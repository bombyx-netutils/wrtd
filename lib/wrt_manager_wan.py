#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import json
import signal
import logging
import socket
from wrt_util import UrlOpenAsync
from wrt_common import WrtCommon
from wrt_common import Managers


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
                                         lambda: Managers.call("on_wconn_up"),
                                         lambda: Managers.call("on_wconn_down"))
                self.wanConnPlugin.start()
                self.logger.info("Internet connection activated, plugin: %s." % (cfgObj["plugin"]))

                with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                    f.write("1")
                self.logger.info("IP forwarding enabled.")
            else:
                self.logger.info("No internet connection configured.")
        except BaseException:
            if self.wanConnPlugin is not None:
                with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                    f.write("0")
                self.wanConnPlugin.stop()
                self.wanConnPlugin = None
                self.logger.info("Internet connection deactivated.")
            raise

    def dispose(self):
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
        self._wconnIpCheckStart()

    def on_wconn_down(self):
        self.wanConnIpIsPublic = None
        if self.wanConnIpChecker is not None:
            self.wanConnIpChecker.cancel()
            self.wanConnIpChecker = None
        self.param.prefixPool.removeExcludePrefixList("wan")

    def _wconnIpCheckStart(self):
        assert self.wanConnIpChecker is None
        self.wanConnIpChecker = UrlOpenAsync("https://ipinfo.io/ip", self._wconnIpCheckComplete, self._wconnIpCheckError)
        self.wanConnIpChecker.start()

    def _wconnIpCheckComplete(self, ip):
        self.wanConnIpIsPublic = (ip == self.wanConnPlugin.get_ip())
        self.logger.error("Internet IP (%s) check complete, %s IP" % (self.wanConnPlugin.get_ip(), "Public" if self.wanConnIpIsPublic else "NATed"))
        self.wanConnIpChecker = None

    def _wconnIpCheckError(self, returncode, msg):
        self.logger.error("Internet IP (%s) check failed, %s" % (self.wanConnPlugin.get_ip(), msg))
        self.wanConnIpChecker = None
        self._wconnIpCheckStart()       # restart check
