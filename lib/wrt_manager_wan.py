#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import shutil
import signal
import socket
import logging
import pyroute2
import ipaddress
from gi.repository import GLib
from gi.repository import GObject
from wrt_util import WrtUtil
from wrt_util import UrlOpenAsync


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

        self.wanConnPluginApi = None
        self.wanConnPlugin = None

        self.wanConnIpChecker = None
        self.wanConnIpCheckRestartTimer = None
        self.wanConnIpIsPublic = None

        try:
            cfgfile = os.path.join(self.param.etcDir, "wan-connection.json")
            if os.path.exists(cfgfile):
                cfgObj = WrtUtil.loadJsonEtcCfg(cfgfile)
                self.wanConnPluginApi = WanConnectionPluginApi(self, cfgObj["plugin"])
                self.wanConnPlugin = self.param.pluginHub.getPlugin("wconn", cfgObj["plugin"])
                self.wanConnPlugin.init2(cfgObj,
                                         self.wanConnPluginApi.get_tmp_dir(),
                                         self.param.ownResolvConf,
                                         lambda: self.param.managerCaller.call("on_wan_conn_up"),
                                         lambda: self.param.managerCaller.call("on_wan_conn_down"))
                self.wanConnPlugin.start()
                self.logger.info("Internet connection activated, plugin: %s." % (cfgObj["plugin"]))
            else:
                self.logger.info("No internet connection configured.")
        except BaseException:
            if self.wanConnPlugin is not None:
                self.wanConnPlugin.stop()
                self.wanConnPlugin = None
                self.logger.info("Internet connection deactivated.")
            if self.wanConnPluginApi is not None:
                self.wanConnPluginApi.dispose()
                self.wanConnPluginApi = None
            raise

    def dispose(self):
        self._wconnIpCheckDispose()
        if self.wanConnPlugin is not None:
            self.wanConnPlugin.stop()
            self.wanConnPlugin = None
            self.logger.info("Internet connection deactivated.")
        if self.wanConnPluginApi is not None:
            self.wanConnPluginApi.dispose()
            self.wanConnPluginApi = None
        self.logger.info("Terminated.")

    def on_wan_conn_up(self):
        # set exclude prefix and restart if neccessary
        wanPrefixList = [WrtUtil.ipMaskToPrefix(self.wanConnPlugin.get_ip(), self.wanConnPlugin.get_netmask())] + self.wanConnPlugin.get_extra_prefix_list()
        if self.param.prefixPool.setExcludePrefixList("wan", wanPrefixList):
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("bridge prefix duplicates with internet connection, autofix it and restart")

        # check dns name
        if self.param.dnsName is not None:
            if socket.gethostbyname(self.param.dnsName) != self.wanConnPlugin.get_ip():
                self.logger.warn("Invalid DNS name %s." % (self.param.dnsName))

        # start checking if ip is public
        self._wconnIpCheckStart()

    def on_wan_conn_down(self):
        self._wconnIpCheckDispose()
        self.param.prefixPool.removeExcludePrefixList("wan")

    def _wconnIpCheckStart(self):
        assert self.wanConnIpChecker is None
        self.wanConnIpChecker = UrlOpenAsync("https://ipinfo.io/ip", self._wconnIpCheckComplete, self._wconnIpCheckError)
        self.wanConnIpChecker.start()

    def _wconnIpCheckComplete(self, ip):
        self.wanConnIpIsPublic = (ip == self.wanConnPlugin.get_ip())
        self.logger.info("Internet IP (%s) check complete, %s IP" % (self.wanConnPlugin.get_ip(), "Public" if self.wanConnIpIsPublic else "NATed"))
        self.wanConnIpChecker = None
        self.param.managerCaller.call("on_wan_ipcheck_complete", self.wanConnIpIsPublic)

    def _wconnIpCheckError(self, returncode, msg):
        self.logger.info("Internet IP (%s) check failed, retry in 10 seconds" % (self.wanConnPlugin.get_ip()))
        self.wanConnIpChecker = None
        self.wanConnIpCheckRestartTimer = GObject.timeout_add_seconds(10, self._wconnIpCheckTimerCallback)     # restart check after 10 seconds

    def _wconnIpCheckTimerCallback(self):
        try:
            self._wconnIpCheckStart()
            self.wanConnIpCheckRestartTimer = None
        except BaseException:
            self.logger.error("Error occured in wan connection ip check timer callback", exc_info=True)
        finally:
            return False

    def _wconnIpCheckDispose(self):
        self.wanConnIpIsPublic = None
        if self.wanConnIpCheckRestartTimer is not None:
            GLib.source_remove(self.wanConnIpCheckRestartTimer)
            self.wanConnIpCheckRestartTimer = None
        if self.wanConnIpChecker is not None:
            self.wanConnIpChecker.cancel()
            self.wanConnIpChecker = None


class WanConnectionPluginApi:

    def __init__(self, parent, pluginName):
        self.parent = parent
        self.tdir = os.path.join(self.parent.param.tmpDir, "wconn-%s" % (pluginName))
        os.mkdir(self.tdir)

    def dispose(self):
        shutil.rmtree(self.tdir)

    def get_tmp_dir(self):
        return self.tdir

    def activate_interface(self, ifname, ifconfig):
        bnet = ipaddress.IPv4Network(ifconfig["prefix"], strict=False)

        with pyroute2.IPRoute() as ipp:
            idx = ipp.link_lookup(ifname=ifname)[0]
            ipp.link("set", index=idx, state="up")
            ipp.addr("add", index=idx, address=bnet.ip, mask=bnet.prefixlen, broadcast=str(bnet.broadcast_address))
            if "gateway" in ifconfig:
                ipp.route('add', dst="0.0.0.0/0", gateway=ifconfig["gateway"], oif=idx)
            if "routes" in ifconfig:
                for rt in ifconfig["routes"]:
                    ipp.route('add', dst=rt["prefix"], gateway=rt["gateway"], oif=idx)

        if "nameservers" in ifconfig:
            with open(self.parent.param.ownResolvConf, "w") as f:
                for ns in ifconfig["nameservers"]:
                    f.write("nameserver %s\n" % (ns))

        self.parent.param.managerCaller.call("on_wan_conn_up", ifname, ifconfig)

    def deactive_interface(self, ifname):
        with open(self.parent.param.ownResolvConf, "w") as f:
            f.write("")

        with pyroute2.IPRoute() as ipp:
            idx = ipp.link_lookup(ifname="ifname")[0]
            ipp.link("set", index=idx, state="down")
            ipp.flush_addr(index=idx)

        self.parent.param.managerCaller.call("on_wan_conn_down", ifname)
