#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import sys
import json
import signal
import shutil
import logging
import traceback
import netifaces
from gi.repository import GLib
from gi.repository import GObject
from dbus.mainloop.glib import DBusGMainLoop
from wrt_util import WrtUtil
from wrt_common import WrtCommon
from wrt_common import PluginHub
from wrt_common import PrefixPool
from wrt_common import ManagerCaller
from wrt_manager_traffic import WrtTrafficManager
from wrt_manager_wan import WrtWanManager
from wrt_manager_lan import WrtLanManager
from wrt_dbus import DbusMainObject
from wrt_dbus import DbusIpForwardObject


class WrtDaemon:

    def __init__(self, param):
        self.param = param
        self.cfgFile = os.path.join(self.param.etcDir, "global.json")
        self.bRestart = False
        self.managerPluginDict = dict()

        self.interfaceDict = dict()
        self.interfaceScanTimeout = 10          # 10 seconds
        self.interfaceTimer = None

    def run(self):
        WrtUtil.ensureDir(self.param.varDir)
        WrtUtil.mkDirAndClear(self.param.tmpDir)
        WrtUtil.mkDirAndClear(self.param.runDir)
        try:
            logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
            logging.getLogger().setLevel(WrtUtil.getLoggingLevel(self.param.logLevel))
            logging.info("Program begins.")

            # load configuration
            self._loadCfg()

            # load UUID
            if WrtCommon.loadUuid(self.param):
                logging.info("UUID generated: \"%s\"." % (self.param.uuid))
            else:
                logging.info("UUID loaded: \"%s\"." % (self.param.uuid))

            # write pid file
            with open(self.param.pidFile, "w") as f:
                f.write(str(os.getpid()))

            # load plugin hub
            self.param.pluginHub = PluginHub(self.param)
            logging.info("Plugin HUB loaded.")

            # load prefix pool
            self.param.prefixPool = PrefixPool(os.path.join(self.param.varDir, "prefix-pool.json"))
            logging.info("Prefix pool loaded.")

            # create nft table
            WrtUtil.shell('/sbin/nft add table ip wrtd')
            WrtUtil.shell('/sbin/nft add chain wrtd fw { type filter hook prerouting priority 0 \\; }')
            WrtUtil.shell('/sbin/nft add chain wrtd natpre { type nat hook prerouting priority 0 \\; }')
            WrtUtil.shell('/sbin/nft add chain wrtd natpost { type nat hook postrouting priority 100 \\; }')      # don't know why priority must be 100, from "https://wiki.nftables.org/wiki-nftables/index.php/Performing_Network_Address_Translation_(NAT)"

            # create our own resolv.conf
            with open(self.param.ownResolvConf, "w") as f:
                f.write("")

            # load manager caller
            self.param.managerCaller = ManagerCaller(self.param)
            logging.info("Manager caller initialized.")

            # create main loop
            DBusGMainLoop(set_as_default=True)
            self.param.mainloop = GLib.MainLoop()

            # business initialize
            self.param.trafficManager = WrtTrafficManager(self.param)
            self.param.wanManager = WrtWanManager(self.param)
            self.param.lanManager = WrtLanManager(self.param)
            self._loadManagerPlugins()
            self.interfaceTimer = GObject.timeout_add_seconds(0, self._interfaceTimerCallback)

            # start DBUS API server
            self.param.dbusMainObject = DbusMainObject(self.param)
            self.param.dbusIpForwardObject = DbusIpForwardObject(self.param)
            logging.info("DBUS-API server started.")

            # start main loop
            logging.info("Mainloop begins.")
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, self._sigHandlerINT, None)
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, self._sigHandlerTERM, None)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGHUP, self._sigHandlerHUP, None)
            self.param.mainloop.run()
            logging.info("Mainloop exits.")
        finally:
            if self.interfaceTimer is not None:
                GLib.source_remove(self.interfaceTimer)
                self.interfaceTimer = None
            if True:
                for p in self.managerPluginDict.values():
                    p.dispose()
                    logging.info("Manager plugin \"%s\" deactivated." % (p.full_name))
                self.managerPluginDict = dict()
            if self.param.lanManager is not None:
                self.param.lanManager.dispose()
                self.param.lanManager = None
            if self.param.wanManager is not None:
                self.param.wanManager.dispose()
                self.param.wanManager = None
            if self.param.trafficManager is not None:
                self.param.trafficManager.dispose()
                self.param.trafficManager = None
            WrtUtil.nftForceDeleteTable("wrtd")
            logging.shutdown()
            shutil.rmtree(self.param.tmpDir)
            if self.bRestart:
                WrtUtil.restartProgram()

    def _sigHandlerINT(self, signum):
        logging.info("SIGINT received.")
        self.param.mainloop.quit()
        return True

    def _sigHandlerTERM(self, signum):
        logging.info("SIGTERM received.")
        self.param.mainloop.quit()
        return True

    def _sigHandlerHUP(self, signum):
        logging.info("SIGHUP received.")
        self.bRestart = True
        self.param.mainloop.quit()
        return True

    def _loadCfg(self):
        if os.path.exists(self.cfgFile):
            cfgObj = None
            with open(self.cfgFile, "r") as f:
                cfgObj = json.load(f)
            self.param.dnsName = cfgObj["dns-name"]

    def _loadManagerPlugins(self):
        # load manager plugin
        for name in self.param.pluginHub.getPluginList("manager"):
            assert name not in self.managerPluginDict
            self.managerPluginDict[name] = self.param.pluginHub.getPlugin("manager", name)

        # get init order
        tlist = []
        for name in self.managerPluginDict:
            bInserted = False
            for i in range(0, len(tlist)):
                if name in self.managerPluginDict[tlist[i]].dependencies:
                    tlist.insert(i, name)
                    bInserted = True
                    break
            if not bInserted:
                tlist.append(name)

        # create manager data
        class _Stub:
            pass
        data = _Stub()
        data.etcDir = self.param.etcDir
        data.tmpDir = self.param.tmpDir
        data.varDir = self.param.varDir
        data.uuid = self.param.uuid
        data.plugin_hub = self.param.pluginHub
        data.prefix_pool = self.param.prefixPool
        data.manager_caller = self.param.managerCaller
        data.managers = {
            "traffic": self.param.trafficManager,
            "wan": self.param.wanManager,
            "lan": self.param.lanManager,
        }
        data.managers.update(self.managerPluginDict)

        # init manager plugin
        for name in tlist:
            fn = os.path.join(self.param.etcDir, "manager-%s.json" % (name))
            if os.path.exists(fn) and os.path.getsize(fn) > 0:
                with open(fn, "r") as f:
                    cfgObj = json.load(f)
            else:
                cfgObj = dict()

            p = self.managerPluginDict[name]
            self.param.managerCaller.add_manager(name, p)                       # order sensitive
            p.init2(cfgObj, self.param.tmpDir, self.param.varDir, data)         # order sensitive
            logging.info("Manager plugin \"%s\" activated." % (p.full_name))

    def _interfaceTimerCallback(self):
        try:
            intfList = netifaces.interfaces()
            intfList = [x for x in intfList if x.startswith("en") or x.startswith("eth") or x.startswith("wl")]

            addList = list(set(intfList) - set(self.interfaceDict.keys()))
            removeList = list(set(self.interfaceDict.keys()) - set(intfList))

            for intf in removeList:
                plugin = self.interfaceDict[intf]
                if plugin is not None:
                    plugin.interface_disappear(intf)
                del self.interfaceDict[intf]

            for intf in addList:
                if self.param.wanManager.wanConnPlugin is not None:
                    # wan connection plugin
                    if self.param.wanManager.wanConnPlugin.interface_appear(intf):
                        self.interfaceDict[intf] = self.param.wanManager.wanConnPlugin
                        continue

                    # lan interface plugin
                    for plugin in self.param.lanManager.lifPluginList:
                        if plugin.interface_appear(self.param.lanManager.defaultBridge, intf):
                            self.interfaceDict[intf] = plugin
                            break
                    if intf in self.interfaceDict:
                        continue

                    # unmanaged interface
                    self.interfaceDict[intf] = None
        except:
            logging.error("Error occured in interface timer callback", traceback.format_exc())
        finally:
            self.interfaceTimer = GObject.timeout_add_seconds(self.interfaceScanTimeout, self._interfaceTimerCallback)
            return False
