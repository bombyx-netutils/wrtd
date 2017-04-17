#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
import dbus
import json
import shutil
import socket
import subprocess
import logging
from wrt_util import WrtUtil
from wrt_common import WrtCommon


class WrtLanManager:

    def __init__(self, param):
        self.param = param
        self.pluginList = []
        self.defaultBridge = None
        self.clientDict = dict()

        logging.info("LAN: Start.")

        try:
            # create default bridge
            tmpdir = os.path.join(self.param.tmpDir, "bridge-default")
            os.mkdir(tmpdir)
            self.defaultBridge = _DefaultBridge(tmpdir, self.param.ownResolvConf)
            self.defaultBridge.start()
            logging.info("LAN: Default bridge established.")

            # start all lan interface plugins
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
                    if cfgFile is not None:
                        with open(cfgFile, "r") as f:
                            cfgObj = json.load(f)

                    tdir = os.path.join(self.param.tmpDir, "lif-%s" % (name))
                    if instanceName != "":
                        tdir += "-%s" % (instanceName)
                    os.mkdir(tdir)

                    p = WrtCommon.getLanInterfacePlugin(self.param, name)
                    self.pluginList.append(p)

                    p.init2(instanceName, cfgObj, self.param.brname, tdir)
                    p.start()
                    logging.info("LAN: Interface plugin \"%s\" activated." % (name))
        except:
            self.dispose()
            raise

    def dispose(self):
        for p in self.pluginList:
            p.stop()
            logging.info("LAN: Interface plugin \"%s\" deactivated." % ("fixme"))
        if self.defaultBridge is not None:
            self.defaultBridge.stop()
            self.defaultBridge = None
            logging.info("LAN: Default bridge destroyed.")
        logging.info("LAN: Terminated.")

    def get_clients(self):
        return self.clientDict.keys()

    def on_client_appear(self, sourceBridgeId, ipDataDict):
        assert all(ip not in self.clientDict for ip in ipDataDict.keys())

        # notify api server
        for ip in ipDataDict.keys():
            self.param.apiServer.addClientIp(ip)

        # notify all bridges
        # note: 1. multiple plugin can share one bridge
        #       2. the source bridge is notified either
        doneList = []
        for plugin in self.pluginList:
            bridge = plugin.get_bridge()
            if bridge is None:
                bridge = self.defaultBridge
            if bridge not in doneList:
                bridge.on_host_appear(sourceBridgeId, ipDataDict)
                doneList.append(bridge)

        # notify downstream
        if self.param.apiServer is not None:
            self.param.apiServer.notifyAppear2(ipDataDict)

        # notify upstream
        self.param.wanManager.on_host_appear(ipDataDict)

        # record
        for ip, data in ipDataDict.items():
            self.clientDict[ip] = data

    def on_client_disappear(self, sourceBridgeId, ipList):
        assert all(ip in self.clientDict for ip in ipDataDict.keys())

        # notify api server
        for ip in ipList:
            self.param.apiServer.removeClientIp(ip)

        # notify all bridges
        # note: 1. multiple plugin can share one bridge
        #       2. the source bridge is notified either
        doneList = []
        for plugin in self.pluginList:
            bridge = plugin.get_bridge()
            if bridge is None:
                bridge = self.defaultBridge
            if bridge not in doneList:
                bridge.on_host_disappear(sourceBridgeId, ipList)
                doneList.append(bridge)

        # notify downstream
        if self.param.apiServer is not None:
            self.param.apiServer.notifyDisappear2(ipList)

        # notify upstream
        self.param.wanManager.on_host_disappear(ipList)

        # record
        for ip in ipList:
            del self.clientDict[ip]


class _DefaultBridge:

    def __init__(self, tmpDir, ownResolvConf, clientAppearFunc, clientChangeFunc, clientDisappearFunc):
        self.tmpDir = tmpDir
        self.ownResolvConf = ownResolvConf
        self.clientAppearFunc = clientAppearFunc
        self.clientChangeFunc = clientChangeFunc
        self.clientDisappearFunc = clientDisappearFunc

        self.brname = "wrtd-br"
        self.ip = "192.168.2.1"
        self.mask = "255.255.255.0"
        self.dhcpRange = ("192.168.2.2", "192.168.2.50")

        self.myhostnameFile = os.path.join(self.tmpDir, "dnsmasq.myhostname")
        self.hostsDir = os.path.join(self.tmpDir, "hosts.d")
        self.leasesFile = os.path.join(self.tmpDir, "dnsmasq.leases")
        self.pidFile = os.path.join(self.tmpDir, "dnsmasq.pid")
        self.dnsmasqProc = None
        self.leaseScanTimer = None
        self.lastScanRecord = None

    def start(self):
        # create bridge interface
        WrtUtil.addBridge(self.brname)
        WrtUtil.setInterfaceUpDown(self.brname, True)
        WrtUtil.shell('/bin/ifconfig "%s" "%s" netmask "%s"' % (self.brname, self.ip, self.mask))

        # start dnsmasq
        self._runDnsmasq()
        with open("/etc/resolv.conf", "w") as f:
            f.write("# Generated by wrtd\n")
            f.write("nameserver 127.0.0.1\n")

    def stop(self):
        with open("/etc/resolv.conf", "w") as f:
            f.write("")
        self._stopDnsmasq()
        WrtUtil.setInterfaceUpDown(self.brname, False)
        WrtUtil.removeBridge(self.brname)

    def get_ip(self):
        return self.ip

    def get_netmask(self):
        return self.mask

    def get_subhost_ip_range(self):
        # return (start_ip, ip_number, count)
        assert False

    def on_bridge_created(self, id):
        with open(os.path.join(self.hostsDir, id), "w") as f:
            pass

    def on_bridge_destroyed(self, id):
        os.unlink(os.path.join(self.hostsDir, id))

    def on_upstream_connected(self, id):
        with open(os.path.join(self.hostsDir, id), "w") as f:
            pass

    def on_upstream_disconnected(self, id):
        os.unlink(os.path.join(self.hostsDir, id))

    def on_host_appear(self, sourceId, ipDataDict):
        if sourceId == self._my_id():
            return

        bChanged = False
        fn = os.path.join(self.hostsDir, sourceId)
        with open(fn, "a") as f:
            for ip, data in ipDataDict.items():
                if "hostname" in data:
                    f.write(ip + " " + hostname + "\n")
                    bChanged = True

        if bChanged:
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def on_host_disappear(self, sourceId, ipList):
        if sourceId == self._my_id():
            return

        fn = os.path.join(self.hostsDir, sourceId)
        bChanged = False

        lineList = []
        with open(fn, "r") as f:
            lineList = f.read().rstrip("\n").split("\n")

        lineList2 = []
        for line in lineList:
            if ip != line.split(" ")[0]:
                lineList2.append(line)
            else:
                bChanged = True

        if bChanged:
            with open(fn, "w") as f:
                for line in lineList2:
                    f.write(line + "\n")
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def _runDnsmasq(self):
        # myhostname file
        with open(self.myhostnameFile, "w") as f:
            f.write("%s %s\n" % (self.ip, socket.gethostname()))

        # make hosts directory
        os.mkdir(self.hostsDir)

        # create empty leases file
        with open(self.leasesFile, "w") as f:
            f.write("")

        # generate dnsmasq config file
        buf = ""
        buf += "strict-order\n"
        buf += "bind-interfaces\n"                            # don't listen on 0.0.0.0
        buf += "interface=lo,%s\n" % (self.brname)
        buf += "user=root\n"
        buf += "group=root\n"
        buf += "\n"
        buf += "dhcp-authoritative\n"
        buf += "dhcp-range=%s,%s,%s,360\n" % (self.param.dhcpRange[0], self.param.dhcpRange[1], self.param.mask)
        buf += "dhcp-option=option:T1,180\n"                                    # strange that dnsmasq's T1=165s, change to 180s which complies to RFC
        buf += "dhcp-leasefile=%s\n" % (self.leasesFile)
        buf += "\n"
        buf += "domain-needed\n"
        buf += "bogus-priv\n"
        buf += "no-hosts\n"
        buf += "resolv-file=%s\n" % (self.ownResolvConf)
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
        os.unlink(self.pidFile)
        os.unlink(self.leasesFile)
        shutil.rmtree(self.hostsDir)
        os.unlink(self.myhostnameFile)

    def _leaseScan(self):
        try:
            ret = set(WrtUtil.readDnsmasqLeaseFile(self.leasesFile))

            # host disappear
            setDisappear = self.lastScanRecord - ret
            ipList = [x[1] for x in setDisappear]
            self.clientDisappearFunc(ipList, self._my_id())

            # host appear
            setAppear = ret - self.lastScanRecord
            ipDataDict = dict()
            for mac, ip, hostname in setAppear:
                ipDataDict[ip] = dict()
                ipDataDict[ip]["wakeup-mac"] = mac
                if hostname != "":
                    ipDataDict[ip]["hostname"] = hostname
            self.clientAppearFunc(ipDataDict, self._my_id())

            self.lastScanRecord = ret
        finally:
            return True

    def _my_id(self):
        return "bridge-" + self.ip
