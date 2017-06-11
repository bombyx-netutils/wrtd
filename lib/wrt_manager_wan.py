#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import json
import signal
import logging
import socket
import pyroute2
import ipaddress
import threading
from collections import OrderedDict
from wrt_util import WrtUtil
from wrt_common import WrtCommon
from wrt_api_cascade import WrtCascadeApiClient


class WrtWanManager:

    # currently:
    # 1. default route is created by plugin
    # 2. self.param.ownResolvConf is created by plugin
    # these are to be modified

    # sub-host change should be dispatched in 10 seconds
    # vpn restart interval is 60 seconds

    def __init__(self, param):
        self.param = param
        self.logger = logging.getLogger(self.__module__ + "." + self.__class__.__name__)
        self.mainThreadId = threading.get_ident()

        self.wanConnPlugin = None

        self.vpnPlugin = None
        self.subHostDict = None                 # dict<upstream-ip, subhost-ip>

        try:
            cfgfile = os.path.join(self.param.etcDir, "wan-connection.json")
            if os.path.exists(cfgfile):
                cfgObj = None
                with open(cfgfile, "r") as f:
                    cfgObj = json.load(f)
                self.wanConnPlugin = WrtCommon.getWanConnectionPlugin(self.param, cfgObj["plugin"])
                tdir = os.path.join(self.param.tmpDir, "wconn-%s" % (cfgObj["plugin"]))
                os.mkdir(tdir)
                self.wanConnPlugin.init2(cfgObj, tdir, self.param.ownResolvConf, self.on_wconn_up, self.on_wconn_down)
                self.wanConnPlugin.start()
                self.logger.info("Internet connection activated, plugin: %s." % (cfgObj["plugin"]))

                with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                    f.write("1")
                self.logger.info("IP forwarding enabled.")
            else:
                self.logger.info("No internet connection configured.")

            cfgfile = os.path.join(self.param.etcDir, "cascade-vpn.json")
            if os.path.exists(cfgfile):
                cfgObj = None
                with open(cfgfile, "r") as f:
                    cfgObj = json.load(f)
                self.vpnPlugin = WrtCommon.getCascadeVpnPlugin(self.param, cfgObj["plugin"])
                tdir = os.path.join(self.param.tmpDir, "wvpn-%s" % (cfgObj["plugin"]))
                os.mkdir(tdir)
                self.vpnPlugin.init2(cfgObj, tdir, self.on_wvpn_up, self.on_wvpn_down)
                self.vpnPlugin.start()
                self.logger.info("Cascade VPN activated, plugin: %s." % (cfgObj["plugin"]))
            else:
                self.logger.info("No cascade VPN configured.")
        except:
            if self.vpnPlugin is not None:
                self.vpnPlugin.stop()
                self.vpnPlugin = None
                self.logger.info("Cascade VPN deactivated.")
            if self.wanConnPlugin is not None:
                with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                    f.write("0")
                self.wanConnPlugin.stop()
                self.wanConnPlugin = None
                self.logger.info("Internet connection deactivated.")
            raise
        self.logger.info("Started.")

    def dispose(self):
        if self.vpnPlugin is not None:
            self.vpnPlugin.stop()
            self.vpnPlugin = None
            self.logger.info("Cascade VPN deactivated.")
        if self.wanConnPlugin is not None:
            with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                f.write("0")
            self.wanConnPlugin.stop()
            self.wanConnPlugin = None
            self.logger.info("Internet connection deactivated.")
        self.logger.info("Terminated.")

    def on_wconn_up(self):
        assert threading.get_ident() == self.mainThreadId

        # set exclude prefix and restart if neccessary
        if self.param.daemon.getPrefixPool().setExcludePrefixList("wan", self.wanConnPlugin.get_prefix_list()):
            self.logger.error("Bridge prefix duplicates with internet connection, restart automatically.")
            os.kill(os.getpid(), signal.SIGHUP)
            return

        # tell other router
        self.param.cascadeManager.wanPrefixListChanged(self.wanConnPlugin.get_prefix_list())

        # change firewall rules
        self.param.trafficManager.set_wan_interface(self.wanConnPlugin.get_interface())

        # check dns name
        if self.param.dnsName is not None:
            if socket.gethostbyname(self.param.dnsName) != self.wanConnPlugin.get_ip():
                self.logger.warn("Invalid DNS name %s." % (self.param.dnsName))

    def on_wconn_down(self):
        assert threading.get_ident() == self.mainThreadId

        # remove firewall rules
        self.param.trafficManager.set_wan_interface(None)

        # tell other router
        self.param.cascadeManager.wanPrefixListChanged([])

        # remove exclude prefix
        self.param.daemon.getPrefixPool().removeExcludePrefixList("wan")

    def on_wvpn_up(self):
        assert threading.get_ident() == self.mainThreadId

        # check vpn prefix and restart if neccessary
        if self.param.daemon.getPrefixPool().setExcludePrefixList("vpn", self.vpnPlugin.get_prefix_list()):
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with VPN connection, autofix it and restart")

        # connect to the upstream cascade api server
        self.param.cascadeManager.startApiClient(self.vpnPlugin.get_remote_ip(),
                                                 self.on_cascade_upstream_client_up,
                                                 self.on_cascade_upstream_client_error,
                                                 self.on_cascade_upstream_router_add,
                                                 self.on_cascade_upstream_router_remove,
                                                 self.on_cascade_upstream_router_wan_prefix_list_change,
                                                 self.on_cascade_upstream_router_lan_prefix_list_change,
                                                 self.on_cascade_upstream_router_client_add_or_change,
                                                 self.on_cascade_upstream_router_client_remove)

    def on_wvpn_down(self):
        assert threading.get_ident() == self.mainThreadId
        self._wvpnDown()

    def on_cascade_upstream_client_up(self, data):
        assert threading.get_ident() == self.mainThreadId

        # get subhost info
        ip1 = ipaddress.IPv4Address(data["subhost-start"])
        ip2 = ipaddress.IPv4Address(data["subhost-end"])
        if ip1 > ip2:
            raise Exception("invalid subhost IP range, %s~%s" % (data["subhost-start"], data["subhost-end"])
        self.subHostDict = dict()
        while ip1 != ip2:
            self.subHostDict[str(ip1)] = None
            ip1 = ip1 + 1
        self.subHostDict[str(ip1)] = None

        # other operation
        self.on_cascade_upstream_router_add(data["router-list"])

    def on_cascade_upstream_client_error(self, reason):
        assert threading.get_ident() == self.mainThreadId

        self.subHostDict = None
        self.vpnPlugin.disconnect()

    def on_cascade_upstream_router_add(self, data):
        assert threading.get_ident() == self.mainThreadId

        # check upstream uuid and restart if neccessary
        if self.param.uuid in self.data.keys():
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("router UUID duplicates, will restart")

        # other operation
        self.on_cascade_upstream_router_wan_prefix_list_change(data)
        self.on_cascade_upstream_router_lan_prefix_list_change(data)
        self.on_cascade_upstream_router_client_add_or_change(data)

    def on_cascade_upstream_router_remove(self, data):
        assert threading.get_ident() == self.mainThreadId

        for router_id in data:
            self.param.daemon.getPrefixPool().removeExcludePrefixList("upstream-lan-%s" % (router_id))
            self.param.daemon.getPrefixPool().removeExcludePrefixList("upstream-wan-%s" % (router_id))

    def on_cascade_upstream_router_wan_prefix_list_change(self, data):
        assert threading.get_ident() == self.mainThreadId

        # check upstream wan-prefix and restart if neccessary
        show_router_id = None
        for router_id, item in data.items():
            if self.param.daemon.getPrefixPool().setExcludePrefixList("upstream-wan-%s" % (router_id), item["wan-prefix-list"]):
                show_router_id = router_id
        if show_router_id is not None:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with upstream router %s, autofix it and restart" % (show_router_id))

    def on_cascade_upstream_router_lan_prefix_list_change(self, data):
        assert threading.get_ident() == self.mainThreadId

        # check upstream lan-prefix and restart if neccessary
        show_router_id = None
        for router_id, item in data.items():
            if self.param.daemon.getPrefixPool().setExcludePrefixList("upstream-lan-%s" % (router_id), item["lan-prefix-list"]):
                show_router_id = router_id
        if show_router_id is not None:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with upstream router %s, autofix it and restart" % (show_router_id))

    def on_cascade_upstream_router_client_add_or_change(self, data):
        assert threading.get_ident() == self.mainThreadId
        pass

    def on_cascade_upstream_router_client_remove(self, data):
        assert threading.get_ident() == self.mainThreadId
        pass

    def on_cascade_downstream_new_router(self, data):
        assert threading.get_ident() == self.mainThreadId

        # other operation
        self.on_cascade_downstream_update_router_wan_prefix_list(data)
        self.on_cascade_downstream_update_router_lan_prefix_list(data)
        self.on_cascade_downstream_new_or_update_router_client(data)

    def on_cascade_downstream_delete_router(self, data):
        assert threading.get_ident() == self.mainThreadId

        for router_id in data:
            self.param.daemon.getPrefixPool().removeExcludePrefixList("downstream-wan-%s" % (router_id))

    def on_cascade_downstream_update_router_wan_prefix_list(self, data):
        assert threading.get_ident() == self.mainThreadId

        # check downstream wan-prefix and restart if neccessary
        show_router_id = None
        for router_id, item in data.items():
            if self.param.daemon.getPrefixPool().setExcludePrefixList("downstream-wan-%s" % (router_id), item["wan-prefix-list"]):
                show_router_id = router_id
        if show_router_id is not None:
            os.kill(os.getpid(), signal.SIGHUP)
            self.logger.error("Prefix duplicates with downstream router %s, autofix it and restart." % (show_router_id))

    def on_cascade_downstream_update_router_lan_prefix_list(self, data):
        assert threading.get_ident() == self.mainThreadId
        # no operation needed

    def on_cascade_downstream_new_or_update_router_client(self, data):
        assert threading.get_ident() == self.mainThreadId
        pass

    def on_cascade_downstream_delete_router_client(self, data):
        assert threading.get_ident() == self.mainThreadId
        pass

    def on_host_appear(self, ipDataDict):
        assert threading.get_ident() == self.mainThreadId

        if self.vpnPlugin is None:
            return
        if self.vpnApiClient is None:
            return

        ipDataDict2 = dict()
        for ip, data in ipDataDict.items():
            empty = None
            for k, v in self.subHostDict.items():
                if v is None and empty is None:
                    empty = k
                    break
            with pyroute2.IPRoute() as ip:
                idx = ip.link_lookup(ifname=self.vpnPlugin.get_interface())[0]
                ip.addr("add", index=idx, address=empty)
            self._addNftRuleVpnSubHost(ip, empty)
            self.subHostDict[empty] = ip
            ipDataDict2[empty] = data
        self.vpnApiClient.addSubhost(ipDataDict2)

    def on_host_disappear(self, ipList):
        assert threading.get_ident() == self.mainThreadId

        if self.vpnPlugin is None:
            return
        if self.vpnApiClient is None:
            return

        ipList2 = []
        for ip in ipList:
            for k, v in self.subHostDict.items():
                if v == ip:
                    self.subHostDict[k] = None
                    self._removeNftRuleSubHost(v, k)
                    with pyroute2.IPRoute() as ip:
                        idx = ip.link_lookup(ifname=self.vpnPlugin.get_interface())[0]
                        ip.addr("delete", index=idx, address=k)
                    ipList2.append(k)
                    break
        self.vpnApiClient.removeSubhost(ipList2)

    def _wvpnDown(self):
        self.param.cascadeManager.disposeApiClient()
        self.param.daemon.getPrefixPool().removeExcludePrefixList("upstream-lan")
        self.param.daemon.getPrefixPool().removeExcludePrefixList("upstream-wan")
        self.subHostDict = None
        self.param.daemon.getPrefixPool().removeExcludePrefixList("vpn")

    def _addNftRuleVpnSubHost(self, subHostIp, natIp):
        WrtUtil.shell('/sbin/nft add rule wrtd natpre ip daddr %s iif %s dnat %s' % (natIp, self.vpnPlugin.get_interface(), subHostIp))
        WrtUtil.shell('/sbin/nft add rule wrtd natpost ip saddr %s oif %s snat %s' % (subHostIp, self.vpnPlugin.get_interface(), natIp))

    def _removeNftRuleSubHost(self, subHostIp, natIp):
        rc, msg = WrtUtil.shell('/sbin/nft list table ip wrtd -a', "retcode+stdout")
        if rc != 0:
            return
        m = re.search("\\s*ip daddr %s iif \"%s\" dnat to %s # handle ([0-9]+)" % (natIp, self.vpnPlugin.get_interface(), subHostIp), msg, re.M)
        if m is not None:
            WrtUtil.shell("/sbin/nft delete rule wrtd natpre handle %s" % (m.group(1)))
        m = re.search("\\s*ip saddr %s oif \"%s\" snat to %s # handle ([0-9]+)" % (subHostIp, self.vpnPlugin.get_interface(), natIp), msg, re.M)
        if m is not None:
            WrtUtil.shell("/sbin/nft delete rule wrtd natpost handle %s" % (m.group(1)))


class _UpStreamInfo:

    def __init__(self, jsonObj):
        self.lanPrefixList = jsonObj["lan-prefix-list"]
        self.wanPrefixList = jsonObj["wan-prefix-list"]
