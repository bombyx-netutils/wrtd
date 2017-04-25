#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import logging
import subprocess
from wrt_util import WrtUtil


class WrtTrafficManager:

    def __init__(self, param):
        self.param = param
        self.cfgFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.conf")
        self.pidFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.pid")

        self.dnsPort = None
        self.dnsmasqProc = None

        self.ownerDict = dict()

        logging.info("TMAN: Start.")

        self._runDnsmasq()
        logging.info("TMAN: Level 2 nameserver started.")

    def dispose(self):
        self._stopDnsmasq()
        logging.info("TMAN: Terminated.")

    def get_l2_nameserver_port(self):
        return self.dnsPort

    def set_data(self, owner, data):
        self.ownerDict[owner] = data

    def delete_data(self, owner):
        del self.ownerDict[owner]

    def _runDnsmasq(self):
        self.dnsPort = WrtUtil.getFreeSocketPort("tcp")

        # generate dnsmasq config file
        buf = ""
        buf += "strict-order\n"
        buf += "bind-interfaces\n"                            # don't listen on 0.0.0.0
        buf += "interface=lo\n"
        buf += "user=root\n"
        buf += "group=root\n"
        buf += "\n"
        buf += "domain-needed\n"
        buf += "bogus-priv\n"
        buf += "no-hosts\n"
        buf += "resolv-file=%s\n" % (self.param.ownResolvConf)
        buf += "\n"
        with open(self.cfgFile, "w") as f:
            f.write(buf)

        # run dnsmasq process
        cmd = "/usr/sbin/dnsmasq"
        cmd += " --keep-in-foreground"
        cmd += " --port=%d" % (self.dnsPort)
        cmd += " --conf-file=\"%s\"" % (self.cfgFile)
        cmd += " --pid-file=%s" % (self.pidFile)
        self.dnsmasqProc = subprocess.Popen(cmd, shell=True, universal_newlines=True)

    def _stopDnsmasq(self):
        if self.dnsmasqProc is not None:
            self.dnsmasqProc.terminate()
            self.dnsmasqProc.wait()
            self.dnsmasqProc = None
        WrtUtil.forceDelete(self.pidFile)
        WrtUtil.forceDelete(self.cfgFile)


class WrtTrafficManagerData:

    def __init__(self):
        self.domainIpDict = dict()                  # <domain-name, ip-address>
        self.domainNsDict = dict()                  # <domain-name, nameserver-list>
        self.webTransparentProxyDict = dict()       # <url-source, url-target>
        self.routeDict = dict()                     # <prefix, (nexthop, interface)>
