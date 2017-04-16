#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import dbus
import random
import zipfile
import socket
from OpenSSL import crypto
from wrt_util import WrtUtil


class SnSubCmdMain:

    def __init__(self, param):
        self.param = param

    def cmdShow(self):
        if not os.path.exists(self.param.tmpDir):
            raise Exception("not started")

        iplist = []
        for fn in glob.glob(os.path.join(self.param.tmpDir, "vpn-*-self.hosts")):
            for ip, hostname in FcsUtil.readDnsmasqHostFile(fn):
                self._showOneClient(ip, hostname)
                iplist.append(ip)
        for fn in glob.glob(os.path.join(self.param.tmpDir, "*.leases")):
            for mac, ip, hostname in FcsUtil.readDnsmasqLeaseFile(fn):
                if ip in iplist:
                    continue
                assert hostname is ""
                self._showOneClient(ip, hostname)

    def _showOneClient(self, ip, hostname):
        if hostname != "":
            hostnameStr = "%s (%s)" % (hostname, ip)
        else:
            hostnameStr = "(%s)" % (ip)
        fname = os.path.join(self.param.tmpDir, "subhosts.d", "owner.%s" % (ip))
        if not os.path.exists(fname):
            print(hostnameStr)
        else:
            print(hostnameStr + ":")
            for sip, shostname in FcsUtil.readDnsmasqHostFile(fname):
                print("    " + shostname + " (" + sip + ")")

    def cmdGenerateClientScript(self, ostype):
        if not FcsCommon.isInitialized(self.param):
            raise Exception("not initialized")

        fn, buf = FcsCommon.generateClientScript(self.param, ostype)
        with open(fn, "w") as f:
            f.write(buf)