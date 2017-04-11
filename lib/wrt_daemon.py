#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import sys
import json
import signal
import shutil
import logging
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop
from wrt_util import WrtUtil
from wrt_dbus import DbusMainObject
from wrt_dbus import DbusIpForwardObject
from wrt_param import WrtConfig
from wrt_param import WrtConfigWifiNetwork
from wrt_common import WrtCommon
from wrt_manager_lan import WrtLanManager
from wrt_manager_wan import WrtWanManager


class WrtDaemon:

    def __init__(self, param):
        self.param = param
        self.mainloop = None

    def run(self):
        WrtUtil.mkDirAndClear(self.param.tmpDir)
        WrtUtil.mkDirAndClear(self.param.runDir)
        try:
            logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
            logging.getLogger().setLevel(WrtUtil.getLoggingLevel(self.param.logLevel))
            logging.info("Program begins.")

            # clean up /etc/hosts
            WrtCommon.cleanupEtcHosts()

            # create main loop
            DBusGMainLoop(set_as_default=True)
            self.param.mainloop = GLib.MainLoop()

            self.param.dbusMainObject = DbusMainObject(self.param)
            self.param.dbusIpForwardObject = DbusIpForwardObject(self.param)

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
            self.param.lanManager = WrtLanManager(self.param)
            self.param.wanManager = WrtWanManager(self.param)

            # start main loop
            logging.info("Mainloop begins.")
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, self._sigHandlerINT, None)
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, self._sigHandlerTERM, None)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGHUP, self._sigHandlerHUP, None)
            self.param.mainloop.run()
            logging.info("Mainloop exits.")
        finally:
            if self.param.wanManager is not None:
                self.param.wanManager.dispose()
            if self.param.lanManager is not None:
                self.param.lanManager.dispose()
            WrtUtil.shell('/sbin/nft delete table wrtd')
            WrtCommon.cleanupEtcHosts()
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