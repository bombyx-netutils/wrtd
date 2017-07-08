#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import json
import signal
import logging
import socket
from wrt_util import WrtUtil
from wrt_util import UrlOpenAsync
from wrt_common import WrtCommon


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

        self.wanConnPlugin = None
        self.wanConnIpChecker = None
        self.wanConnIpIsPublic = None

        self.vpnPlugin = None

        self.downstreamDict = dict()

        try:
            cfgfile = os.path.join(self.param.etcDir, "wan-connection.json")
            if os.path.exists(cfgfile):
                cfgObj = None
                with open(cfgfile, "r") as f:
                    cfgObj = json.load(f)
                self.wanConnPlugin = WrtCommon.getWanConnectionPlugin(self.param, cfgObj["plugin"])
                tdir = os.path.join(self.param.tmpDir, "wconn-%s" % (cfgObj["plugin"]))
                os.mkdir(tdir)
                self.wanConnPlugin.init2(cfgObj,
                                         tdir,
                                         self.param.ownResolvConf,
                                         lambda: WrtCommon.callManagers(self.param, "on_wconn_up"),
                                         lambda: WrtCommon.callManagers(self.param, "on_wconn_down"))
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
                self.vpnPlugin.init2(cfgObj,
                                     tdir,
                                     lambda: WrtCommon.callManagers(self.param, "on_wvpn_up"),
                                     lambda: WrtCommon.callManagers(self.param, "on_wvpn_down"))
                self.logger.info("CASCADE-VPN activated, plugin: %s." % (cfgObj["plugin"]))
            else:
                self.logger.info("No CASCADE-VPN configured.")
        except BaseException:
            if self.vpnPlugin is not None:
                self.vpnPlugin = None
                self.logger.info("CASCADE-VPN deactivated.")
            if self.wanConnPlugin is not None:
                with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                    f.write("0")
                self.wanConnPlugin.stop()
                self.wanConnPlugin = None
                self.logger.info("Internet connection deactivated.")
            raise

    def dispose(self):
        if self.vpnPlugin is not None:
            self.vpnPlugin.stop()
            self.vpnPlugin = None
            self.logger.info("CASCADE-VPN deactivated.")
        if self.wanConnPlugin is not None:
            with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                f.write("0")
            self.wanConnPlugin.stop()
            self.wanConnPlugin = None
            self.logger.info("Internet connection deactivated.")
        self.logger.info("Terminated.")

    def on_wconn_up(self):
        # set exclude prefix and restart if neccessary
        if self.param.prefixPool.setExcludePrefixList("wan", self.wanConnPlugin.get_prefix_list()):
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("bridge prefix duplicates with internet connection, autofix it and restart")

        # check dns name
        if self.param.dnsName is not None:
            if socket.gethostbyname(self.param.dnsName) != self.wanConnPlugin.get_ip():
                self.logger.warn("Invalid DNS name %s." % (self.param.dnsName))

        # start checking if ip is public
        self.wconnIpChecker = UrlOpenAsync("https://ipinfo.io/ip", self._wconnIpCheckComplete, self._wconnIpCheckError)
        self.wconnIpChecker.start()

        # start vpn plugin
        if self.vpnPlugin is not None:
            self.vpnPlugin.start()

    def on_wconn_down(self):
        self.wanConnIpIsPublic = None
        if self.vpnPlugin is not None:
            self.vpnPlugin.stop()
        if self.wconnIpChecker is not None:
            self.wconnIpChecker.cancel()
            self.wconnIpChecker = None
        self.param.prefixPool.removeExcludePrefixList("wan")

    def on_wvpn_up(self):
        if WrtUtil.prefixListConflict(self.vpnPlugin.get_prefix_list(), self.wanConnPlugin.get_prefix_list()):
            raise Exception("cascade-VPN prefix duplicates with internet connection")

        # check vpn prefix and restart if neccessary
        if self.param.prefixPool.setExcludePrefixList("vpn", self.vpnPlugin.get_prefix_list()):
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("bridge prefix duplicates with CASCADE-VPN connection, autofix it and restart")

    def on_wvpn_down(self):
        self.param.prefixPool.removeExcludePrefixList("vpn")

    def on_cascade_upstream_fail(self, excp):
        self.vpnPlugin.disconnect()

    def on_cascade_upstream_down(self):
        self.vpnPlugin.disconnect()

    def on_cascade_downstream_up(self, peer_uuid, data):
        self.downstreamDict[peer_uuid] = []
        self.on_cascade_downstream_router_add(peer_uuid, data["router-list"])

    def on_cascade_downstream_down(self, peer_uuid):
        self.on_cascade_downstream_router_remove(peer_uuid, self.downstreamDict[peer_uuid])
        del self.downstreamDict[peer_uuid]

    def on_cascade_downstream_router_add(self, peer_uuid, data):
        self.downstreamDict[peer_uuid] += data.keys()
        self.on_cascade_downstream_router_wan_prefix_list_changed(peer_uuid, data)

    def on_cascade_downstream_router_remove(self, peer_uuid, data):
        for router_id in data:
            self.param.prefixPool.removeExcludePrefixList("downstream-wan-%s" % (router_id))
            self.downstreamDict[peer_uuid].remove(router_id)

    def on_cascade_downstream_router_wan_prefix_list_changed(self, peer_uuid, data):
        # check downstream wan-prefix and restart if neccessary
        show_router_id = None
        for router_id, item in data.items():
            if "wan-prefix-list" not in item:
                continue        # used when called by on_cascade_downstream_router_add()
            if self.param.prefixPool.setExcludePrefixList("downstream-wan-%s" % (router_id), item["wan-prefix-list"]):
                show_router_id = router_id
        if show_router_id is not None:
            os.kill(os.getpid(), signal.SIGHUP)
            self.logger.error("Prefix duplicates with downstream router %s, autofix it and restart." % (show_router_id))

    def _wconnIpCheckComplete(self, ip):
        self.wanConnIpIsPublic = (ip == self.wanConnPlugin.get_ip())
        self.wanConnIpChecker = None

    def _wconnIpCheckError(self, returncode, msg):
        self.logger.error("Internet IP check failed, %s" % (msg))
        self.wanConnIpChecker = None
