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
        self.vpnApiClient = None
        self.vpnUpstreamDict = None             # ordereddict<upstream-id, data>
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

        # check prefix and tell upstream
        if self.wanConnPlugin.is_alive() and self.vpnUpstreamDict is not None:
            plist = []
            for p1 in sum(self.vpnUpstreamDict.values()):
                for p2 in self.wanConnPlugin.get_prefix_list():
                    if WrtUtil.prefixConflic(p1, p2):
                        plist.append(p1)
            if len(plist) > 0:
                self.logger.error("Upstream prefix duplicates with internet connection, tell upstream and restart myself (ah, unfair).")
                self.vpnApiClient.prefixConflict(plist)
                os.kill(os.getpid(), signal.SIGHUP)
                return

        # change firewall rules
        self.param.trafficManager.set_wan_interface(self.wanConnPlugin.get_interface())

    def on_wconn_down(self):
        assert threading.get_ident() == self.mainThreadId

        # remove firewall rules
        self.param.trafficManager.set_wan_interface(None)

        # remove exclude prefix
        self.param.daemon.getPrefixPool().removeExcludePrefixList("wan")

    def on_wvpn_up(self):
        assert threading.get_ident() == self.mainThreadId

        class _Excp1(Exception):
            pass

        class _Excp2(Exception):
            pass

        def _RestartVpn():
            self.vpnPlugin.stop()
            self.vpnPlugin.start()

        try:
            # check vpn prefix and restart if neccessary
            if self.param.daemon.getPrefixPool().setExcludePrefixList("vpn", self.vpnPlugin.get_prefix_list()):
                self.logger.error("Bridge prefix duplicates with VPN connection, restart automatically.")
                raise _Excp1()

            # connect to the upstream cascade api server
            self.vpnApiClient = WrtCascadeApiClient(self.vpnPlugin.get_remote_ip(), self.param.cascadeApiPort)
            initData = None
            try:
                initData = self.vpnApiClient.connect()
            except socket.error as e:
                self.logger.error("Cascade API error: %s. Restart VPN plugin.", e)
                raise _Excp2()

            # get upstream info
            self.vpnUpstreamDict = OrderedDict()
            for k, v in initData["upstream"]:
                self.vpnUpstreamDict[k] = _UpStreamInfo(v)

            # get subhost info
            self.subHostDict = dict()
            if True:
                ip1 = ipaddress.IPv4Address(initData["subhost-start"])
                ip2 = ipaddress.IPv4Address(initData["subhost-end"])
                if ip1 > ip2:
                    self.logger.error("Cascade API error: invalid subhost IP range. Restart VPN plugin.")
                    raise _Excp2()
                while ip1 != ip2:
                    self.subHostDict[str(ip1)] = None
                    ip1 = ip1 + 1
                self.subHostDict[str(ip1)] = None

            # check upstream uuid and restart if neccessary
            if self.param.uuid in self.vpnUpstreamDict.keys():
                self.logger.error("Router UUID duplicates with upstream, restart automatically.")
                raise _Excp1()

            # check upstream wan-prefix and restart if neccessary
            tl = sum([x.wanPrefixList for x in self.vpnUpstreamDict.values()])
            if self.param.daemon.getPrefixPool().setExcludePrefixList("upstream-wan", tl):
                self.logger.error("Bridge prefix duplicates with upstream, restart automatically.")
                raise _Excp1()

            # check upstream lan-prefix and restart if neccessary
            tl = sum([x.lanPrefixList for x in self.vpnUpstreamDict.values()])
            if self.param.daemon.getPrefixPool().setExcludePrefixList("upstream-lan", tl):
                self.logger.error("Bridge prefix duplicates with upstream, restart automatically.")
                raise _Excp1()

            # check prefix and tell upstream
            if self.wanConnPlugin.is_alive():
                plist = []
                for p1 in sum(self.vpnUpstreamDict.values()):
                    for p2 in self.wanConnPlugin.get_prefix_list():
                        if WrtUtil.prefixConflic(p1, p2):
                            plist.append(p1)
                if len(plist) > 0:
                    self.logger.error("Upstream prefix duplicates with internet connection, tell upstream and restart myself (ah, unfair).")
                    self.vpnApiClient.prefixConflict(plist)
                    raise _Excp1()
        except _Excp1:
            self._wvpnDown()
            os.kill(os.getpid(), signal.SIGHUP)
        except _Excp2:
            self._wvpnDown()
            WrtUtil.idleInvoke(_RestartVpn)

    def on_wvpn_down(self):
        assert threading.get_ident() == self.mainThreadId
        self._wvpnDown()

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
        self.param.daemon.getPrefixPool().removeExcludePrefixList("upstream-lan")
        self.param.daemon.getPrefixPool().removeExcludePrefixList("upstream-wan")

        self.subHostDict = None
        self.vpnUpstreamDict = None

        if self.vpnApiClient is not None:
            self.vpnApiClient.dispose()
            self.vpnApiClient = None

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
