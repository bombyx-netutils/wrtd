#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
import signal
import json
import socket
import subprocess
import logging
import ipaddress
import pyroute2
from collections import OrderedDict
from gi.repository import GLib
from gi.repository import GObject
from wrt_util import WrtUtil
from wrt_common import WrtCommon


class WrtLanManager:

    def __init__(self, param):
        self.param = param
        self.pluginDict = OrderedDict()             # <name, object>
        self.defaultBridge = None
        self.clientDict = dict()

        logging.info("LAN: Start.")

        try:
            # create default bridge
            tmpdir = os.path.join(self.param.tmpDir, "bridge-default")
            os.mkdir(tmpdir)
            vardir = os.path.join(self.param.varDir, "bridge-default")
            WrtUtil.ensureDir(vardir)
            self.defaultBridge = _DefaultBridge(tmpdir, vardir)
            self.defaultBridge.init2("wrtd-br",
                                     self.param.daemon.getPrefixPool().usePrefix(),
                                     self.param.trafficManager.get_l2_nameserver_port(),
                                     self.on_client_appear,
                                     self.on_client_change,
                                     self.on_client_disappear)
            logging.info("LAN: Default bridge started.")

            # start all lan interface plugins
            bridgeNo = 2
            for name in WrtCommon.getLanInterfacePluginList(self.param):
                tlist = []
                for fn in glob.glob(os.path.join(self.param.etcDir, "lan-interface-%s*.json" % (name))):
                    bn = os.path.basename(fn)
                    instanceName = bn[len("lan-interface-%s" % (name)):len(".json") * -1]
                    if instanceName != "":
                        instanceName = instanceName.lstrip("-")
                    tlist.append((instanceName, fn))
                if len(tlist) == 0:
                    tlist.append(("", None))

                for instanceName, cfgFile in tlist:
                    cfgObj = dict()
                    if cfgFile is not None and os.path.getsize(cfgFile) > 0:
                        with open(cfgFile, "r") as f:
                            cfgObj = json.load(f)

                    if instanceName != "":
                        tname = "%s-%s" % (name, instanceName)
                    else:
                        tname = name
                    tmpdir = os.path.join(self.param.tmpDir, "lif-%s" % (tname))
                    os.mkdir(tmpdir)
                    vardir = os.path.join(self.param.varDir, "lif-%s" % (tname))
                    WrtUtil.ensureDir(vardir)

                    p = WrtCommon.getLanInterfacePlugin(self.param, name)
                    p.init2(instanceName, cfgObj, tmpdir, vardir)
                    if p.get_bridge() is not None:
                        p.get_bridge().init2("wrtd-br%d" % (bridgeNo),
                                             self.param.daemon.getPrefixPool().usePrefix(),
                                             self.param.trafficManager.get_l2_nameserver_port(),
                                             self.on_client_appear,
                                             self.on_client_change,
                                             self.on_client_disappear)
                        bridgeNo += 1
                    p.start()

                    self.pluginDict[tname] = p
                    logging.info("LAN: Interface plugin \"%s\" activated." % (tname))
        except:
            self.dispose()
            raise

    def dispose(self):
        for tname, p in self.pluginDict.items():
            if p.get_bridge() is not None:
                p.get_bridge().dispose()
            p.stop()
            logging.info("LAN: Interface plugin \"%s\" deactivated." % (tname))
        if self.defaultBridge is not None:
            self.defaultBridge.dispose()
            self.defaultBridge = None
            logging.info("LAN: Default bridge destroyed.")
        logging.info("LAN: Terminated.")

    def get_plugins(self):
        return self.pluginDict.values()

    def get_bridges(self):
        ret = set()
        for plugin in self.pluginDict.values():
            bridge = plugin.get_bridge()
            if bridge is None:
                ret.add(self.defaultBridge)
            else:
                ret.add(bridge)
        return list(ret)

    def get_clients(self):
        return self.clientDict.keys()

    def on_client_appear(self, sourceBridgeId, ipDataDict):
        assert all(ip not in self.clientDict for ip in ipDataDict.keys())

        # record
        for ip, data in ipDataDict.items():
            self.clientDict[ip] = data

        # notify all bridges
        for bridge in self.get_bridges():
            if sourceBridgeId == bridge.get_bridge_id():
                continue
            bridge.on_host_appear(sourceBridgeId, ipDataDict)

        # notify my clients
        if self.param.sgwApiServer is not None:
            self.param.sgwApiServer.notifyAppear2(ipDataDict)

        # notify subhost owners
        pass

        # notify upstream
        self.param.wanManager.on_host_appear(ipDataDict)

    def on_client_change(self, sourceBridgeId, ipDataDict):
        assert False

    def on_client_disappear(self, sourceBridgeId, ipList):
        assert all(ip in self.clientDict for ip in ipList)

        # record
        for ip in ipList:
            del self.clientDict[ip]

        # notify all bridges
        for bridge in self.get_bridges():
            if sourceBridgeId == bridge.get_bridge_id():
                continue
            bridge.on_host_disappear(sourceBridgeId, ipList)

        # notify my clients
        if self.param.sgwApiServer is not None:
            self.param.sgwApiServer.notifyDisappear2(ipList)

        # notify subhost owners
        pass

        # notify upstream
        self.param.wanManager.on_host_disappear(ipList)


class _DefaultBridge:

    def __init__(self, tmpDir, varDir):
        self.tmpDir = tmpDir
        self.varDir = varDir
        self.l2DnsPort = None
        self.clientAppearFunc = None
        self.clientChangeFunc = None
        self.clientDisappearFunc = None

        self.brname = None
        self.brnetwork = None
        self.dhcpRange = None
        self.subhostIpRange = None

        self.myhostnameFile = os.path.join(self.tmpDir, "dnsmasq.myhostname")
        self.hostsDir = os.path.join(self.tmpDir, "hosts.d")
        self.leasesFile = os.path.join(self.tmpDir, "dnsmasq.leases")
        self.pidFile = os.path.join(self.tmpDir, "dnsmasq.pid")
        self.dnsmasqProc = None
        self.leaseScanTimer = None
        self.lastScanRecord = None

    def init2(self, brname, prefix, l2DnsPort, clientAppearFunc, clientChangeFunc, clientDisappearFunc):
        assert prefix[1] == "255.255.255.0"

        self.brname = brname
        self.brnetwork = ipaddress.IPv4Network(prefix)

        self.brip = ipaddress.IPv4Address(prefix[0]) + 1
        self.dhcpRange = (self.brip + 1, self.brip + 49)
        self.subhostIpRange = []
        i = 51
        while i + 49 < 255:
            self.subhostIpRange.append((self.brip + i, self.brip + i + 49))
            i += 50

        self.l2DnsPort = l2DnsPort
        self.clientAppearFunc = clientAppearFunc
        self.clientChangeFunc = clientChangeFunc
        self.clientDisappearFunc = clientDisappearFunc

        # create bridge interface
        with pyroute2.IPRoute() as ip:
            ip.link("add", kind="bridge", ifname=self.brname)
            idx = ip.link_lookup(ifname=self.brname)[0]
            ip.link("set", index=idx, state="up")
            ip.addr("add", index=idx, address=self.brip, mask=self.brnetwork.prefixlen, broadcast=self.brnetwork.broadcast_address)

        # start dnsmasq
        self._runDnsmasq()
        with open("/etc/resolv.conf", "w") as f:
            f.write("# Generated by wrtd\n")
            f.write("nameserver 127.0.0.1\n")

    def dispose(self):
        with open("/etc/resolv.conf", "w") as f:
            f.write("")
        self._stopDnsmasq()
        with pyroute2.IPRoute() as ip:
            idx = ip.link_lookup(ifname=self.brname)[0]
            ip.link("set", index=idx, state="down")
            ip.link("del", index=idx)

    def get_name(self):
        return self.brname

    def get_bridge_id(self):
        return "bridge-" + self.brip

    def get_prefix(self):
        return (self.brnetwork.network_address, self.brnetwork.netmask)

    def get_ip(self):
        return self.self.brip

    def get_subhost_ip_range(self):
        return self.subhostIpRange

    def on_other_bridge_created(self, id):
        with open(os.path.join(self.hostsDir, id), "w") as f:
            f.write("")

    def on_other_bridge_destroyed(self, id):
        os.unlink(os.path.join(self.hostsDir, id))

    def on_subhost_owner_connected(self, id):
        with open(os.path.join(self.hostsDir, id), "w") as f:
            f.write("")

    def on_subhost_owner_disconnected(self, id):
        os.unlink(os.path.join(self.hostsDir, id))

    def on_upstream_connected(self, id):
        with open(os.path.join(self.hostsDir, id), "w") as f:
            f.write("")

    def on_upstream_disconnected(self, id):
        os.unlink(os.path.join(self.hostsDir, id))

    def on_host_appear(self, sourceId, ipDataDict):
        bChanged = False
        fn = os.path.join(self.hostsDir, sourceId)
        with open(fn, "a") as f:
            for ip, data in ipDataDict.items():
                if "hostname" in data:
                    f.write(ip + " " + data["hostname"] + "\n")
                    bChanged = True

        if bChanged:
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def on_host_disappear(self, sourceId, ipList):
        fn = os.path.join(self.hostsDir, sourceId)
        bChanged = False

        lineList = []
        with open(fn, "r") as f:
            lineList = f.read().rstrip("\n").split("\n")

        lineList2 = []
        for line in lineList:
            if line.split(" ")[0] not in ipList:
                lineList2.append(line)
            else:
                bChanged = True

        if bChanged:
            with open(fn, "w") as f:
                for line in lineList2:
                    f.write(line + "\n")
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def on_host_refresh(self, sourceId, ipDataDict):
        fn = os.path.join(self.hostsDir, sourceId)

        buf = ""
        with open(fn, "r") as f:
            buf = f.read()

        buf2 = ""
        for ip, data in ipDataDict.items():
            if "hostname" in data:
                buf2 += ip + " " + data["hostname"] + "\n"

        if buf != buf2:
            with open(fn, "w") as f:
                f.write(buf2)
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def _runDnsmasq(self):
        # myhostname file
        with open(self.myhostnameFile, "w") as f:
            f.write("%s %s\n" % (self.brip, socket.gethostname()))

        # make hosts directory
        os.mkdir(self.hostsDir)

        # create empty leases file
        with open(self.leasesFile, "w") as f:
            f.write("")

        # generate dnsmasq config file
        buf = ""
        buf += "strict-order\n"
        buf += "bind-interfaces\n"                                       # don't listen on 0.0.0.0
        buf += "interface=lo,%s\n" % (self.brname)
        buf += "user=root\n"
        buf += "group=root\n"
        buf += "\n"
        buf += "dhcp-authoritative\n"
        buf += "dhcp-range=%s,%s,%s,360\n" % (self.dhcpRange[0], self.dhcpRange[1], self.brnetwork.netmask)
        buf += "dhcp-option=option:T1,180\n"                             # strange that dnsmasq's T1=165s, change to 180s which complies to RFC
        buf += "dhcp-leasefile=%s\n" % (self.leasesFile)
        buf += "\n"
        buf += "domain-needed\n"
        buf += "bogus-priv\n"
        buf += "no-hosts\n"
        buf += "server=127.0.0.1#%d\n" % (self.l2DnsPort)
        buf += "addn-hosts=%s\n" % (self.hostsDir)                       # "hostsdir=" only adds record, no deletion, so not usable
        buf += "addn-hosts=%s\n" % (self.myhostnameFile)                 # we use addn-hosts which has no inotify, and we send SIGHUP to dnsmasq when host file changes
        buf += "\n"
        cfgf = os.path.join(self.tmpDir, "dnsmasq.conf")
        with open(cfgf, "w") as f:
            f.write(buf)

        # run dnsmasq process
        cmd = "/usr/sbin/dnsmasq"
        cmd += " --keep-in-foreground"
        cmd += " --conf-file=\"%s\"" % (cfgf)
        cmd += " --pid-file=%s" % (self.pidFile)
        self.dnsmasqProc = subprocess.Popen(cmd, shell=True, universal_newlines=True)

        self.lastScanRecord = set()
        self.leaseScanTimer = GObject.timeout_add_seconds(10, self._leaseScan)

    def _stopDnsmasq(self):
        if self.leaseScanTimer is not None:
            GLib.source_remove(self.leaseScanTimer)
            self.leaseScanTimer = None
            self.lastScanRecord = None
        if self.dnsmasqProc is not None:
            self.dnsmasqProc.terminate()
            self.dnsmasqProc.wait()
            self.dnsmasqProc = None
        WrtUtil.forceDelete(self.pidFile)
        WrtUtil.forceDelete(self.leasesFile)
        WrtUtil.forceDelete(self.hostsDir)
        WrtUtil.forceDelete(self.myhostnameFile)

    def _leaseScan(self):
        try:
            ret = set(WrtUtil.readDnsmasqLeaseFile(self.leasesFile))

            # host disappear
            setDisappear = self.lastScanRecord - ret
            ipList = [x[1] for x in setDisappear]
            self.clientDisappearFunc(ipList, self.get_bridge_id())

            # host appear
            setAppear = ret - self.lastScanRecord
            ipDataDict = dict()
            for mac, ip, hostname in setAppear:
                ipDataDict[ip] = dict()
                ipDataDict[ip]["wakeup-mac"] = mac
                if hostname != "":
                    ipDataDict[ip]["hostname"] = hostname
            self.clientAppearFunc(ipDataDict, self.get_bridge_id())

            self.lastScanRecord = ret
        finally:
            return True
