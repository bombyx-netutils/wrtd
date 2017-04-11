#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os


class WrtParam:

    def __init__(self):
        self.etcDir = "/etc/wrtd"
        self.libDir = "/usr/lib/wrtd"
        self.dataDir = "/usr/share/wrtd"
        self.runDir = "/run/wrtd"
        self.logDir = "/var/log/wrtd"
        self.tmpDir = "/tmp/wrtd"

        self.cfgFile = os.path.join(self.etcDir, "config.json")
        self.ownResolvConf = os.path.join(self.tmpDir, "resolv.conf")

        self.mainloop = None
        self.dbusMainObject = None
        self.dbusIpForwardObject = None

        self.brname = "wrtb"
        self.ip = "192.168.2.1"
        self.net = "192.168.2.0"
        self.mask = "255.255.255.0"
        self.baddr = "192.168.2.255"
        self.dhcpRange = ("192.168.2.100", "192.168.2.254")

        self.vpnIntf = "vpnc"
        self.vpnApiPort = 2220

        self.sgwApiPort = 2300

        self.pidFile = os.path.join(self.runDir, "wrtd.pid")
        self.logLevel = None
        self.config = None
        self.pluginManager = None
        self.lanManager = None
        self.wanManager = None
