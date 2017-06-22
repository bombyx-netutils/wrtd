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
from gi.repository import GLib
from gi.repository import GObject
from wrt_util import WrtUtil
from wrt_common import WrtCommon


class WrtLanManager:

    def __init__(self, param):
        self.param = param
        self.defaultBridge = None
        self.lifPluginList = []
        self.vpnsPluginList = []
        self.downstreamDict = dict()

        try:
            # create default bridge
            tmpdir = os.path.join(self.param.tmpDir, "bridge-default")
            os.mkdir(tmpdir)
            vardir = os.path.join(self.param.varDir, "bridge-default")
            WrtUtil.ensureDir(vardir)
            self.defaultBridge = _DefaultBridge(tmpdir, vardir)
            self.defaultBridge.init2("wrtd-br",
                                     self.param.prefixPool.usePrefix(),
                                     self.param.trafficManager.get_l2_nameserver_port(),
                                     lambda source_id, ip_data_dict: WrtCommon.callManagers(self.param, "on_client_add_or_change", source_id, ip_data_dict),
                                     lambda source_id, ip_list: WrtCommon.callManagers(self.param, "on_client_remove", source_id, ip_list))
            logging.info("Default bridge started.")

            # start all lan interface plugins
            for name in WrtCommon.getLanInterfacePluginList(self.param):
                for instanceName, cfgObj, tmpdir, vardir in self._getInstanceAndInfoFromEtcDir("lif", "lan-interface", name):
                    os.mkdir(tmpdir)
                    WrtUtil.ensureDir(vardir)

                    p = WrtCommon.getLanInterfacePlugin(self.param, name, instanceName)
                    p.init2(instanceName, cfgObj, tmpdir, vardir)
                    p.start()
                    self.lifPluginList.append(p)
                    logging.info("LAN interface plugin \"%s\" activated." % (p.full_name))

            # start all vpn server plugins
            for name in WrtCommon.getVpnServerPluginList(self.param):
                for instanceName, cfgObj, tmpdir, vardir in self._getInstanceAndInfoFromEtcDir("vpns", "vpn-server", name):
                    os.mkdir(tmpdir)
                    WrtUtil.ensureDir(vardir)

                    p = WrtCommon.getVpnServerPlugin(self.param, name, instanceName)
                    p.init2(instanceName,
                            cfgObj,
                            tmpdir,
                            vardir,
                            self.param.prefixPool.usePrefix(),
                            self.param.trafficManager.get_l2_nameserver_port(),
                            lambda source_id, ip_data_dict: WrtCommon.callManagers(self.param, "on_client_add_or_change", source_id, ip_data_dict),
                            lambda source_id, ip_list: WrtCommon.callManagers(self.param, "on_client_remove", source_id, ip_list),
                            lambda x: self._apiFirewallAllowFunc(p.full_name, x))
                    p.start()
                    self.vpnsPluginList.append(p)
                    logging.info("VPN server plugin \"%s\" activated." % (p.full_name))

            # get all bridges
            all_bridges = [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]

            # send other-bridge-create event
            for bridge in all_bridges:
                for other_bridge in all_bridges:
                    if bridge == other_bridge:
                        continue
                    bridge.on_source_add(other_bridge.get_bridge_id())
        except BaseException:
            self._dispose()
            raise

    def dispose(self):
        self._dispose()
        logging.info("Terminated.")

    def on_client_add_or_change(self, source_id, ip_data_dict):
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            if source_id == bridge.get_bridge_id():
                continue
            bridge.on_host_add_or_change(source_id, ip_data_dict)

    def on_client_remove(self, source_id, ip_list):
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            if source_id == bridge.get_bridge_id():
                continue
            bridge.on_host_remove(source_id, ip_list)

    def on_cascade_upstream_up(self, data):
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            bridge.on_source_add("upstream-vpn")
        self._upstreamVpnHostRefresh()

    def on_cascade_upstream_down(self):
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            bridge.on_source_remove("upstream-vpn")

    def on_cascade_upstream_router_add(self, data):
        self._upstreamVpnHostRefresh()

    def on_cascade_upstream_router_remove(self, data):
        self._upstreamVpnHostRefresh()

    def on_cascade_upstream_router_client_add_or_change(self, data):
        self._upstreamVpnHostRefresh()

    def on_cascade_upstream_router_client_remove(self, data):
        self._upstreamVpnHostRefresh()

    def on_cascade_downstream_up(self, peer_uuid, data):
        self.downstreamDict[peer_uuid] = []
        self.on_cascade_downstream_new_router(peer_uuid, data)

    def on_cascade_downstream_down(self, peer_uuid):
        if len(self.downstreamDict[peer_uuid]) > 0:
            self.on_cascade_downstream_delete_router(peer_uuid, self.downstreamDict[peer_uuid])
        del self.downstreamDict[peer_uuid]

    def on_cascade_downstream_new_router(self, peer_uuid, data):
        for router_id in data.keys():
            self.downstreamDict[peer_uuid].append(router_id)
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_source_add("downstream-" + router_id)
        self.on_cascade_downstream_new_or_update_router_client(data)

    def on_cascade_downstream_delete_router(self, peer_uuid, data):
        for router_id in data:
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_source_remove("downstream-" + router_id)
            self.downstreamDict[peer_uuid].remove(router_id)

    def on_cascade_downstream_new_or_update_router_client(self, peer_uuid, data):
        for router_id, info in data:
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_host_add_or_change("downstream-" + router_id, info["client-list"])

    def on_cascade_downstream_delete_router_client(self, peer_uuid, data):
        for router_id, info in data:
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_host_remove("downstream-" + router_id, info["client-list"])

    def _apiFirewallAllowFunc(self, owner, rule):
        class _Stub:
            pass
        data = _Stub
        data.firewall_allow = [rule]
        self.param.trafficManager.set_data(owner, data)

    def _upstreamVpnHostRefresh(self):
        ipDataDict = dict()
        for router in self.param.cascadeManager.apiClient.routerInfo.values():
            for ip, data in router["client-list"].items():
                if "nat-ip" in data:
                    ip = data["nat-ip"]
                    data = data.copy()
                    del data["nat-ip"]
                ipDataDict[ip] = data
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            bridge.on_host_refresh("upstream-vpn", ipDataDict)

    def _getInstanceAndInfoFromEtcDir(self, pluginPrefix, cfgfilePrefix, name):
        # Returns (instanceName, cfgobj, tmpdir, vardir)

        ret = []
        for fn in glob.glob(os.path.join(self.param.etcDir, "%s-%s*.json" % (cfgfilePrefix, name))):
            bn = os.path.basename(fn)

            instanceName = bn[len("%s-%s" % (cfgfilePrefix, name)):len(".json") * -1]
            if instanceName != "":
                instanceName = instanceName.lstrip("-")

            if instanceName != "":
                fullName = "%s-%s" % (name, instanceName)
            else:
                fullName = name

            if os.path.getsize(fn) > 0:
                with open(fn, "r") as f:
                    cfgObj = json.load(f)
            else:
                cfgObj = dict()

            tmpdir = os.path.join(self.param.tmpDir, "%s-%s" % (pluginPrefix, fullName))
            vardir = os.path.join(self.param.varDir, "%s-%s" % (pluginPrefix, fullName))

            ret.append((instanceName, cfgObj, tmpdir, vardir))

        if len(ret) == 0:
            instanceName = ""
            fullName = name
            cfgObj = dict()
            tmpdir = os.path.join(self.param.tmpDir, "%s-%s" % (pluginPrefix, fullName))
            vardir = os.path.join(self.param.varDir, "%s-%s" % (pluginPrefix, fullName))
            ret.append((instanceName, cfgObj, tmpdir, vardir))

        return ret

    def _dispose(self):
        for p in self.vpnsPluginList:
            p.stop()
            logging.info("VPN server plugin \"%s\" deactivated." % (p.full_name))
        self.vpnsPluginList = []

        for p in self.lifPluginList:
            p.stop()
            logging.info("LAN interface plugin \"%s\" deactivated." % (p.full_name))
        self.lifPluginList = []

        if self.defaultBridge is not None:
            self.defaultBridge.dispose()
            self.defaultBridge = None
            logging.info("Default bridge destroyed.")


class _DefaultBridge:

    def __init__(self, tmpDir, varDir):
        self.tmpDir = tmpDir
        self.varDir = varDir
        self.l2DnsPort = None
        self.clientAppearFunc = None
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

    def init2(self, brname, prefix, l2DnsPort, clientAppearFunc, clientDisappearFunc):
        assert prefix[1] == "255.255.255.0"

        self.brname = brname
        self.brnetwork = ipaddress.IPv4Network(prefix[0] + "/" + prefix[1])

        self.brip = ipaddress.IPv4Address(prefix[0]) + 1
        self.dhcpRange = (self.brip + 1, self.brip + 49)

        self.l2DnsPort = l2DnsPort
        self.clientAppearFunc = clientAppearFunc
        self.clientDisappearFunc = clientDisappearFunc

        # create bridge interface
        with pyroute2.IPRoute() as ip:
            ip.link("add", kind="bridge", ifname=self.brname)
            idx = ip.link_lookup(ifname=self.brname)[0]
            ip.link("set", index=idx, state="up")
            ip.addr("add", index=idx, address=str(self.brip), mask=self.brnetwork.prefixlen, broadcast=str(self.brnetwork.broadcast_address))

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
        return "bridge-%s" % (self.brip)

    def get_prefix(self):
        return (str(self.brnetwork.network_address), str(self.brnetwork.netmask))

    def get_subhost_ip_range(self):
        subhostIpRange = []
        i = 51
        while i + 49 < 255:
            subhostIpRange.append((str(self.brip + i), str(self.brip + i + 49)))
            i += 50
        return subhostIpRange

    def on_source_add(self, source_id):
        with open(os.path.join(self.hostsDir, source_id), "w") as f:
            f.write("")

    def on_source_remove(self, source_id):
        os.unlink(os.path.join(self.hostsDir, source_id))

    def on_host_add_or_change(self, sourceId, ipDataDict):
        bChanged = False
        fn = os.path.join(self.hostsDir, sourceId)
        with open(fn, "a") as f:
            for ip, data in ipDataDict.items():
                if "hostname" in data:
                    f.write(ip + " " + data["hostname"] + "\n")
                    bChanged = True

        if bChanged:
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def on_host_remove(self, sourceId, ipList):
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
