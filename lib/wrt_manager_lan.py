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
        assert len(ip_data_dict) > 0
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            if source_id == bridge.get_bridge_id():
                continue
            bridge.on_host_add_or_change(source_id, ip_data_dict)

    def on_client_remove(self, source_id, ip_list):
        assert len(ip_list) > 0
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
        self.on_cascade_downstream_new_router(peer_uuid, data["router-list"])

    def on_cascade_downstream_down(self, peer_uuid):
        if len(self.downstreamDict[peer_uuid]) > 0:
            self.on_cascade_downstream_delete_router(peer_uuid, self.downstreamDict[peer_uuid])
        del self.downstreamDict[peer_uuid]

    def on_cascade_downstream_new_router(self, peer_uuid, data):
        for router_id in data.keys():
            self.downstreamDict[peer_uuid].append(router_id)
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_source_add("downstream-" + router_id)
            self._downstreamVpnHostRefreshForRouter(peer_uuid, router_id)

    def on_cascade_downstream_delete_router(self, peer_uuid, data):
        for router_id in data:
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_source_remove("downstream-" + router_id)

    def on_cascade_downstream_new_or_update_router_client(self, peer_uuid, data):
        for router_id in data.keys():
            self._downstreamVpnHostRefreshForRouter(peer_uuid, router_id)

    def on_cascade_downstream_delete_router_client(self, peer_uuid, data):
        for router_id in data.keys():
            self._downstreamVpnHostRefreshForRouter(peer_uuid, router_id)

    def _apiFirewallAllowFunc(self, owner, rule):
        class _Stub:
            pass
        data = _Stub
        data.firewall_allow = [rule]
        self.param.trafficManager.set_data(owner, data)

    def _upstreamVpnHostRefresh(self):
        # we need to differentiate upstream router and other client, so we do refresh instead of add/change/remove
        ipDataDict = dict()

        # add upstream routers into ipDataDict
        upstreamRouterLocalIpList = []
        if self.param.cascadeManager.hasValidApiClient():
            curUpstreamId = self.param.cascadeManager.apiClient.get_peer_uuid()
            curUpstreamIp = self.param.cascadeManager.apiClient.get_peer_ip()
            curUpstreamLocalIp = self.param.wanManager.vpnPlugin.get_local_ip()
            while True:
                data = self.param.cascadeManager.apiClient.get_upstream_router_info()[curUpstreamId]

                ipDataDict[curUpstreamIp] = dict()
                if "hostname" in data:
                    ipDataDict[curUpstreamIp]["hostname"] = data["hostname"]
                upstreamRouterLocalIpList.append(curUpstreamLocalIp)

                if "parent" not in data:
                    break
                curUpstreamId = data["parent"]
                curUpstreamIp = data["cascade-vpn"]["remote-ip"]
                curUpstreamLocalIp = data["cascade-vpn"]["local-ip"]

        # add all clients into ipDataDict
        for router in self.param.cascadeManager.apiClient.get_upstream_router_info().values():
            if "client-list" in router:
                for ip, data in router["client-list"].items():
                    if ip in upstreamRouterLocalIpList:
                        continue
                    if "nat-ip" in data:
                        ip = data["nat-ip"]
                        data = data.copy()
                        del data["nat-ip"]
                    ipDataDict[ip] = data

        # refresh to all bridges
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            bridge.on_host_refresh("upstream-vpn", ipDataDict)

    def _downstreamVpnHostRefreshForRouter(self, peer_uuid, router_id):
        # we don't want to record "nat-ip" information, so we do refresh instead of add/change/remove
        ipDataDict = dict()

        # get router data
        routerData = None
        for sproc in self.param.cascadeManager.getAllValidApiServerProcessors():
            if sproc.get_peer_uuid() == peer_uuid:
                for id2, data2 in sproc.get_downstream_router_info().items():
                    if id2 == router_id:
                        routerData = data2
                        break
                if routerData is not None:
                    break
        assert routerData is not None

        # add all clients into ipDataDict
        for ip, data in routerData["client-list"].items():
            if "nat-ip" in data:
                ip = data["nat-ip"]
                data = data.copy()
                del data["nat-ip"]
            ipDataDict[ip] = data

        # refresh to all bridges
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            bridge.on_host_refresh("downstream-" + router_id, ipDataDict)

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

        self.serverFile = os.path.join(self.tmpDir, "cmd.socket")
        self.cmdSock = None
        self.cmdSockWatch = None

        self.myhostnameFile = os.path.join(self.tmpDir, "dnsmasq.myhostname")
        self.hostsDir = os.path.join(self.tmpDir, "hosts.d")
        self.leasesFile = os.path.join(self.tmpDir, "dnsmasq.leases")
        self.pidFile = os.path.join(self.tmpDir, "dnsmasq.pid")
        self.dnsmasqProc = None

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

        # start cmd server
        self._runCmdServer()

    def dispose(self):
        self._stopCmdServer()
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

    def on_host_add_or_change(self, source_id, ip_data_dict):
        fn = os.path.join(self.hostsDir, source_id)
        bChanged = False

        itemDict = OrderedDict()
        with open(fn, "r") as f:
            for line in f.read().rstrip("\n").split("\n"):
                itemDict[line.split(" ")[0]] = line.split(" ")[1]

        for ip, data in ip_data_dict.items():
            if ip in itemDict:
                if "hostname" in data:
                    if itemDict[ip] != data["hostname"]:
                        itemDict[ip] = data["hostname"]
                        bChanged = True
                else:
                    del itemDict[ip]
                    bChanged = True
            else:
                if "hostname" in data:
                    itemDict[ip] = data["hostname"]
                    bChanged = True

        if bChanged:
            with open(fn, "w") as f:
                for ip, hostname in itemDict.items():
                    f.write(ip + " " + hostname + "\n")
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def on_host_remove(self, source_id, ip_list):
        fn = os.path.join(self.hostsDir, source_id)
        bChanged = False

        lineList = []
        with open(fn, "r") as f:
            lineList = f.read().rstrip("\n").split("\n")

        lineList2 = []
        for line in lineList:
            if line.split(" ")[0] not in ip_list:
                lineList2.append(line)
            else:
                bChanged = True

        if bChanged:
            with open(fn, "w") as f:
                for line in lineList2:
                    f.write(line + "\n")
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def on_host_refresh(self, source_id, ip_data_dict):
        fn = os.path.join(self.hostsDir, source_id)

        itemDict = dict()
        with open(fn, "r") as f:
            for line in f.read().rstrip("\n").split("\n"):
                itemDict[line.split(" ")[0]] = line.split(" ")[1]

        itemDict2 = dict()
        for ip, data in ip_data_dict.items():
            if "hostname" in data:
                itemDict[ip] = data["hostname"]

        if itemDict != itemDict2:
            with open(fn, "w") as f:
                for ip, hostname in itemDict2:
                    f.write(ip + " " + data["hostname"] + "\n")
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def _runCmdServer(self):
        self.cmdSock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.cmdSock.bind(self.serverFile)
        self.cmdSockWatch = GLib.io_add_watch(self.cmdSock, GLib.IO_IN, self.__cmdServerWatch)

    def _stopCmdServer(self):
        if self.cmdSockWatch is not None:
            GLib.source_remove(self.cmdSockWatch)
            self.cmdSockWatch = None
        if self.cmdSock is not None:
            self.cmdSock.close()
            self.cmdSock = None

    def _runDnsmasq(self):
        selfdir = os.path.dirname(os.path.realpath(__file__))

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
        buf += "dhcp-script=%s\n" % (os.path.join(selfdir, "dhcp-script.py"))
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

    def _stopDnsmasq(self):
        if self.dnsmasqProc is not None:
            self.dnsmasqProc.terminate()
            self.dnsmasqProc.wait()
            self.dnsmasqProc = None
        WrtUtil.forceDelete(self.pidFile)
        WrtUtil.forceDelete(self.leasesFile)
        WrtUtil.forceDelete(self.hostsDir)
        WrtUtil.forceDelete(self.myhostnameFile)

    def __cmdServerWatch(self, source, cb_condition):
        try:
            buf = self.cmdSock.recvfrom(4096)[0].decode("utf-8")
            jsonObj = json.loads(buf)
            if jsonObj["cmd"] == "add-or-change":
                # notify lan manager
                data = dict()
                data[jsonObj["ip"]] = dict()
                if "hostname" in jsonObj:
                    data[jsonObj["ip"]]["hostname"] = jsonObj["hostname"]
                self.clientAppearFunc(self.get_bridge_id(), data)
            elif jsonObj["cmd"] == "remove":
                # notify lan manager
                data = [jsonObj["ip"]]
                self.clientDisappearFunc(self.get_bridge_id(), data)
            else:
                assert False
        except:
            logging.error("receive error", exc_info=True)       # fixme
        finally:
            return True
