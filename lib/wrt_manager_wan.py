#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import shutil
import signal
import logging
import pyroute2
from wrt_util import WrtUtil


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

        self.ifconfigDict = dict()      # dict<ifname,ifconfig>

        try:
            cfgfile = os.path.join(self.param.etcDir, "wan-connection.json")
            if os.path.exists(cfgfile):
                cfgObj = WrtUtil.loadJsonEtcCfg(cfgfile)
                self.wanConnPluginApi = WanConnectionPluginApi(self, cfgObj["plugin"])
                self.wanConnPlugin = self.param.pluginHub.getPlugin("wconn", cfgObj["plugin"])
                self.wanConnPlugin.start(cfgObj, self.wanConnPluginApi)
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
        wanPrefixList = []
        for ifc in self.ifconfigDict.values():
            wanPrefixList.append(WrtUtil.ipMaskToPrefix(ifc["prefix"].split("/")[0], ifc["prefix"].split("/")[1]))
        if self.param.prefixPool.setExcludePrefixList("wan", wanPrefixList):
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("bridge prefix duplicates with internet connection, autofix it and restart")

    def on_wan_conn_down(self):
        self.param.prefixPool.removeExcludePrefixList("wan")

    # FIXME
    def get_interface(self):
        assert len(self.ifconfigDict) == 1
        return list(self.ifconfigDict.keys())[0]

    # FIXME
    def is_connected(self):
        return len(self.ifconfigDict) > 0

    # FIXME
    def get_ip(self):
        assert len(self.ifconfigDict) == 1
        return list(self.ifconfigDict.values())[0]["prefix"].split("/")[0]


class WanConnectionPluginApi:

    def __init__(self, parent, pluginName):
        self.parent = parent
        self.tdir = os.path.join(self.parent.param.tmpDir, "wconn-%s" % (pluginName))
        os.mkdir(self.tdir)

    def dispose(self):
        shutil.rmtree(self.tdir)

    def get_tmp_dir(self):
        return self.tdir

    def add_ntfac(self, ntfac_name, ntfac_object):
        pass

    def remove_ntfac(self, ntfac_name, ntfac_object):
        pass

    def activate_interface(self, ifname, ifconfig):
        with pyroute2.IPRoute() as ipp:
            idx = ipp.link_lookup(ifname=ifname)[0]
            if "gateway" in ifconfig:
                ipp.route('add', dst="0.0.0.0/0", gateway=ifconfig["gateway"], oif=idx)
            if "routes" in ifconfig:
                for rt in ifconfig["routes"]:
                    ipp.route('add', dst=rt["prefix"], gateway=rt["gateway"], oif=idx)

        if "nameservers" in ifconfig:
            with open(self.parent.param.ownResolvConf, "w") as f:
                for ns in ifconfig["nameservers"]:
                    f.write("nameserver %s\n" % (ns))

        self.parent.ifconfigDict[ifname] = ifconfig

        self.parent.param.managerCaller.call("on_wan_conn_up")

    def deactive_interface(self, ifname):
        del self.parent.ifconfigDict[ifname]

        with open(self.parent.param.ownResolvConf, "w") as f:
            f.write("")

        self.parent.param.managerCaller.call("on_wan_conn_down")
