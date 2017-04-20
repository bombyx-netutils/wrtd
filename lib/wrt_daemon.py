#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import sys
import signal
import shutil
import logging
import netifaces
from gi.repository import GLib
from gi.repository import GObject
from dbus.mainloop.glib import DBusGMainLoop
from wrt_util import WrtUtil
from wrt_common import WrtCommon
from wrt_manager_traffic import WrtTrafficManager
from wrt_manager_lan import WrtLanManager
from wrt_manager_wan import WrtWanManager
from wrt_api_dbus import DbusMainObject
from wrt_api_dbus import DbusIpForwardObject
from wrt_api_sgw import WrtSgwApiServer
from wrt_api_cascade import WrtCascadeApiServer


class WrtDaemon:

    def __init__(self, param):
        self.param = param
        self.mainloop = None
        self.interfaceDict = dict()
        self.interfaceTimer = None

    def run(self):
        WrtUtil.mkDirAndClear(self.param.tmpDir)
        WrtUtil.mkDirAndClear(self.param.runDir)
        try:
            logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
            logging.getLogger().setLevel(WrtUtil.getLoggingLevel(self.param.logLevel))
            logging.info("Program begins.")

            # create main loop
            DBusGMainLoop(set_as_default=True)
            self.param.mainloop = GLib.MainLoop()

            # write pid file
            with open(self.param.pidFile, "w") as f:
                f.write(str(os.getpid()))

            # create nft table
            WrtUtil.shell('/sbin/nft add table ip wrtd')
            WrtUtil.shell('/sbin/nft add chain wrtd fw { type filter hook prerouting priority 0 \\; }')
            WrtUtil.shell('/sbin/nft add chain wrtd natpre { type nat hook prerouting priority 0 \\; }')
            WrtUtil.shell('/sbin/nft add chain wrtd natpost { type nat hook postrouting priority 100 \\; }')      # don't know why priority must be 100, from "https://wiki.nftables.org/wiki-nftables/index.php/Performing_Network_Address_Translation_(NAT)"

            # create our own resolv.conf
            with open(self.param.ownResolvConf, "w") as f:
                f.write("")

            # business initialize
            self.param.trafficManager = WrtTrafficManager(self.param)
            self.param.wanManager = WrtWanManager(self.param)
            self.param.lanManager = WrtLanManager(self.param)
            self.interfaceTimer = GObject.timeout_add_seconds(10, self._interfaceTimerCallback)

            # start DBUS API server
            self.param.dbusMainObject = DbusMainObject(self.param)
            self.param.dbusIpForwardObject = DbusIpForwardObject(self.param)
            logging.info("DBUS-API server started.")

            # start SGW API server
            self.param.sgwApiServer = WrtSgwApiServer(self.param)
            logging.info("SGW-API server started.")

            # start CASCADE API server
            for bridge in self.param.lanManager.get_bridges():
                self.param.cascadeApiServerList.append(WrtCascadeApiServer(self.param, bridge))
            logging.info("CASCADE-API servers started.")

            # start main loop
            logging.info("Mainloop begins.")
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, self._sigHandlerINT, None)
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, self._sigHandlerTERM, None)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGHUP, self._sigHandlerHUP, None)
            self.param.mainloop.run()
            logging.info("Mainloop exits.")
        finally:
            if self.param.sgwApiServer is not None:
                self.param.sgwApiServer.dispose()
            if self.interfaceTimer is not None:
                GLib.source_remove(self.interfaceTimer)
            if self.param.lanManager is not None:
                self.param.lanManager.dispose()
            if self.param.wanManager is not None:
                self.param.wanManager.dispose()
            WrtUtil.shell('/sbin/nft delete table wrtd')
            logging.shutdown()
            shutil.rmtree(self.param.tmpDir)

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
        self.bDataChanged = True
        if self.vpnClientProc is not None:
            self.vpnClientProc.terminate()
        return True

    def _interfaceTimerCallback(self):
        intfList = netifaces.interfaces()
        intfList = [x for x in intfList if x.startswith("en") or x.startswith("wl")]

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
                for plugin in self.param.lanManager.pluginList:
                    bridge = plugin.get_bridge()
                    if bridge is None:
                        bridge = self.param.lanManager.defaultBridge
                    if plugin.interface_appear(bridge, intf):
                        self.interfaceDict[intf] = plugin
                        break
                if intf in self.interfaceDict:
                    continue

                # unmanaged interface
                self.interfaceDict[intf] = None

        return True
