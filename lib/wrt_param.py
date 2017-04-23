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
        self.varDir = "/var/wrtd"

        self.cfgFile = os.path.join(self.etcDir, "config.json")
        self.ownResolvConf = os.path.join(self.tmpDir, "resolv.conf")

        self.uuid = None

        self.mainloop = None
        self.dbusMainObject = None
        self.dbusIpForwardObject = None

        self.sgwApiPort = 2220
        self.cascadeApiPort = 2221

        self.pidFile = os.path.join(self.runDir, "wrtd.pid")
        self.logLevel = None
        self.config = None

        self.daemon = None
        self.trafficManager = None
        self.lanManager = None
        self.wanManager = None
        self.sgwApiServer = None
        self.cascadeApiServerList = []
