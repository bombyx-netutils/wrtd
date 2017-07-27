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
from gi.repository import Gio
from wrt_util import WrtUtil
from wrt_common import WrtCommon
from wrt_common import Managers


class WrtLanManager:

    def __init__(self, param):
        self.param = param
        self.defaultBridge = None
        self.lanServDict = dict()           # dict<name,json-object>
        self.lifPluginList = []
        self.vpnsPluginList = []

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
                                     lambda source_id, ip_data_dict: Managers.call("on_client_add", source_id, ip_data_dict),
                                     lambda source_id, ip_data_dict: Managers.call("on_client_change", source_id, ip_data_dict),
                                     lambda source_id, ip_list: Managers.call("on_client_remove", source_id, ip_list))
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
                            lambda source_id, ip_data_dict: Managers.call("on_client_add", source_id, ip_data_dict),
                            lambda source_id, ip_data_dict: Managers.call("on_client_change", source_id, ip_data_dict),
                            lambda source_id, ip_list: Managers.call("on_client_remove", source_id, ip_list))
                    p.start()
                    self.vpnsPluginList.append(p)
                    logging.info("VPN server plugin \"%s\" activated." % (p.full_name))

                    if p.get_wan_service() is not None:
                        self.param.trafficManager.add_wan_service(p.full_name, p.get_wan_service())

            # send other-bridge-create event
            all_bridges = [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]
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

    def add_lan_service(self, service):
        service_id = 0
        for i in self.lanServDict.keys():
            service_id = max(service_id, i + 1)
        assert service_id not in self.lanServDict.keys()

        self.lanServDict[service_id] = service
        return service_id

    def remove_lan_service(self, service_id):
        del self.lanServDict[service_id]

    def on_client_add(self, source_id, ip_data_dict):
        assert len(ip_data_dict) > 0
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            if source_id == bridge.get_bridge_id():
                continue
            bridge.on_host_add(source_id, ip_data_dict)

    def on_client_change(self, source_id, ip_data_dict):
        assert len(ip_data_dict) > 0
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            if source_id == bridge.get_bridge_id():
                continue
            bridge.on_host_change(source_id, ip_data_dict)

    def on_client_remove(self, source_id, ip_list):
        assert len(ip_list) > 0
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            if source_id == bridge.get_bridge_id():
                continue
            bridge.on_host_remove(source_id, ip_list)

    def on_cascade_upstream_up(self, api_client, data):
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            bridge.on_source_add("upstream-vpn")
        self._upstreamVpnHostRefresh(api_client)

    def on_cascade_upstream_down(self, api_client):
        for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
            bridge.on_source_remove("upstream-vpn")

    def on_cascade_upstream_router_add(self, api_client, data):
        self._upstreamVpnHostRefresh(api_client)

    def on_cascade_upstream_router_remove(self, api_client, data):
        self._upstreamVpnHostRefresh(api_client)

    def on_cascade_upstream_router_client_add(self, api_client, data):
        self._upstreamVpnHostRefresh(api_client)

    def on_cascade_upstream_router_client_change(self, api_client, data):
        self._upstreamVpnHostRefresh(api_client)

    def on_cascade_upstream_router_client_remove(self, api_client, data):
        self._upstreamVpnHostRefresh(api_client)

    def on_cascade_downstream_up(self, sproc, data):
        self.on_cascade_downstream_router_add(sproc, data["router-list"])

    def on_cascade_downstream_down(self, sproc):
        self.on_cascade_downstream_router_remove(sproc, list(sproc.get_router_info().keys()))

    def on_cascade_downstream_router_add(self, sproc, data):
        for router_id, router_info in data.items():
            if "client-list" not in router_info:
                continue
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_source_add("downstream-" + router_id)
                bridge.on_host_add("downstream-" + router_id, router_info["client-list"])

    def on_cascade_downstream_router_remove(self, sproc, data):
        for router_id in data:
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_source_remove("downstream-" + router_id)

    def on_cascade_downstream_router_client_add(self, sproc, data):
        for router_id, router_info in data.items():
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_host_add("downstream-" + router_id, router_info["client-list"])

    def on_cascade_downstream_router_client_change(self, sproc, data):
        for router_id, router_info in data.items():
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_host_change("downstream-" + router_id, router_info["client-list"])

    def on_cascade_downstream_router_client_remove(self, sproc, data):
        for router_id, router_info in data.items():
            for bridge in [self.defaultBridge] + [x.get_bridge() for x in self.vpnsPluginList]:
                bridge.on_host_remove("downstream-" + router_id, router_info["client-list"])

    def _upstreamVpnHostRefresh(self, api_client):
        # we need to differentiate upstream router and other client, so we do refresh instead of add/change/remove
        ipDataDict = dict()

        # add upstream routers into ipDataDict
        upstreamRouterLocalIpList = []
        if self.param.cascadeManager.hasValidApiClient():
            curUpstreamId = api_client.get_peer_uuid()
            curUpstreamIp = api_client.get_peer_ip()
            curUpstreamLocalIp = self.param.wanManager.vpnPlugin.get_local_ip()
            while True:
                data = api_client.get_router_info()[curUpstreamId]

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
        for router in api_client.get_router_info().values():
            if "client-list" in router:
                for ip, data in router["client-list"].items():
                    if ip in upstreamRouterLocalIpList:
                        continue
                    ipDataDict[ip] = data

        # refresh to all bridges
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
        self.clientAddFunc = None
        self.clientChangeFunc = None
        self.clientRemoveFunc = None

        self.brname = None
        self.brnetwork = None
        self.dhcpRange = None

        self.myhostnameFile = os.path.join(self.tmpDir, "dnsmasq.myhostname")
        self.hostsDir = os.path.join(self.tmpDir, "hosts.d")
        self.leasesFile = os.path.join(self.tmpDir, "dnsmasq.leases")
        self.pidFile = os.path.join(self.tmpDir, "dnsmasq.pid")
        self.dnsmasqProc = None
        self.leaseMonitor = None
        self.lastScanRecord = None

    def init2(self, brname, prefix, l2dns_port, client_add_func, client_change_func, client_remove_func):
        assert prefix[1] == "255.255.255.0"

        self.brname = brname
        self.brnetwork = ipaddress.IPv4Network(prefix[0] + "/" + prefix[1])

        self.brip = ipaddress.IPv4Address(prefix[0]) + 1
        self.dhcpRange = (self.brip + 1, self.brip + 49)

        self.l2DnsPort = l2dns_port
        self.clientAddFunc = client_add_func
        self.clientChangeFunc = client_change_func
        self.clientRemoveFunc = client_remove_func

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

    def on_source_add(self, source_id):
        with open(os.path.join(self.hostsDir, source_id), "w") as f:
            f.write("")

    def on_source_remove(self, source_id):
        os.unlink(os.path.join(self.hostsDir, source_id))

    def on_host_add(self, source_id, ip_data_dict):
        fn = os.path.join(self.hostsDir, source_id)
        itemDict = WrtUtil.dnsmasqHostFileToOrderedDict(fn)
        bChanged = False

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
            WrtUtil.dictToDnsmasqHostFile(itemDict, fn)
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def on_host_change(self, source_id, ip_data_dict):
        self.on_host_add(source_id, ip_data_dict)

    def on_host_remove(self, source_id, ip_list):
        fn = os.path.join(self.hostsDir, source_id)
        itemDict = WrtUtil.dnsmasqHostFileToOrderedDict(fn)
        bChanged = False

        for ip in ip_list:
            if ip in itemDict:
                del itemDict[ip]
                bChanged = True

        if bChanged:
            WrtUtil.dictToDnsmasqHostFile(itemDict, fn)
            self.dnsmasqProc.send_signal(signal.SIGHUP)

    def on_host_refresh(self, source_id, ip_data_dict):
        fn = os.path.join(self.hostsDir, source_id)
        itemDict = WrtUtil.dnsmasqHostFileToDict(fn)

        itemDict2 = dict()
        for ip, data in ip_data_dict.items():
            if "hostname" in data:
                itemDict2[ip] = data["hostname"]

        if itemDict != itemDict2:
            WrtUtil.dictToDnsmasqHostFile(itemDict2, fn)
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

        # monitor dnsmasq lease file
        self.leaseMonitor = Gio.File.new_for_path(self.leasesFile).monitor(0, None)
        self.leaseMonitor.connect("changed", self._dnsmasqLeaseChanged)
        self.lastScanRecord = []

    def _stopDnsmasq(self):
        self.lastScanRecord = None
        if self.leaseMonitor is not None:
            self.leaseMonitor.cancel()
            self.leaseMonitor = None
        if self.dnsmasqProc is not None:
            self.dnsmasqProc.terminate()
            self.dnsmasqProc.wait()
            self.dnsmasqProc = None
        WrtUtil.forceDelete(self.pidFile)
        WrtUtil.forceDelete(self.leasesFile)
        WrtUtil.forceDelete(self.hostsDir)
        WrtUtil.forceDelete(self.myhostnameFile)

    def _dnsmasqLeaseChanged(self, monitor, file, other_file, event_type):
        if event_type != Gio.FileMonitorEvent.CHANGED:
            return

        try:
            newLeaseList = WrtUtil.readDnsmasqLeaseFile(self.leasesFile)

            addList = []
            changeList = []
            removeList = []
            for item in newLeaseList:
                item2 = self.___dnsmasqLeaseChangedFind(item, self.lastScanRecord)
                if item2 is not None:
                    if item[1] != item2[1] or item[3] != item2[3]:      # mac or hostname change
                        changeList.append(item)
                else:
                    addList.append(item)
            for item in self.lastScanRecord:
                if self.___dnsmasqLeaseChangedFind(item, newLeaseList) is None:
                    removeList.append(item)

            if len(addList) > 0:
                ipDataDict = dict()
                for expiryTime, mac, ip, hostname, clientId in addList:
                    self.__dnsmasqLeaseChangedAddToIpDataDict(ipDataDict, ip, mac, hostname)
                    if hostname != "":
                        logging.info("Client %s(IP:%s, MAC:%s) appeared." % (hostname, ip, mac))
                    else:
                        logging.info("Client %s(%s) appeared." % (ip, mac))
                for expiryTime, mac, ip, hostname, clientId in changeList:
                    self.__dnsmasqLeaseChangedAddToIpDataDict(ipDataDict, ip, mac, hostname)
                    # log is not needed for client change
                self.clientAddFunc(self.get_bridge_id(), ipDataDict)

            if len(changeList) > 0:
                ipDataDict = dict()
                for expiryTime, mac, ip, hostname, clientId in changeList:
                    self.__dnsmasqLeaseChangedAddToIpDataDict(ipDataDict, ip, mac, hostname)
                    # log is not needed for client change
                self.clientChangeFunc(self.get_bridge_id(), ipDataDict)

            if len(removeList) > 0:
                ipList = [x[2] for x in removeList]
                self.clientRemoveFunc(self.get_bridge_id(), ipList)
                for expiryTime, mac, ip, hostname, clientId in removeList:
                    if hostname != "":
                        logging.info("Client %s(IP:%s, MAC:%s) disappeared." % (hostname, ip, mac))
                    else:
                        logging.info("Client %s(%s) disappeared." % (ip, mac))

            self.lastScanRecord = newLeaseList
        except Exception as e:
            logging.error("Lease scan failed", exc_info=True)      # fixme

    def ___dnsmasqLeaseChangedFind(self, item, leaseList):
        for item2 in leaseList:
            if item2[2] == item[2]:     # compare by ip
                return item2
        return None

    def __dnsmasqLeaseChangedAddToIpDataDict(self, ipDataDict, ip, mac, hostname):
        ipDataDict[ip] = dict()
        ipDataDict[ip]["wakeup-mac"] = mac
        if hostname != "":
            ipDataDict[ip]["hostname"] = hostname
