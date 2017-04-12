#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
import fcntl
from wrt_util import WrtUtil


class WrtCommon:

    @staticmethod
    def cleanupEtcHosts():
        bNoOp = True
        lineList = []
        lineList2 = []
        with open("/etc/hosts", "r") as f:
            b = -1
            for line in f.read().split("\n"):
                if line == "### wrtd begin ###":
                    b = 0
                    bNoOp = False
                if b == -1:
                    lineList.append(line)
                if b == 1:
                    lineList2.append(line)
                if line == "### wrtd end ###":
                    b = 1
                    bNoOp = False
        if bNoOp:
            return

        lineList += lineList2
        while len(lineList) > 0 and lineList[-1] == "":
            del lineList[-1]

        with open("/etc/hosts", "w") as f:
            f.write("\n".join(lineList))
            f.write("\n")

    @staticmethod
    def syncToEtcHosts(tmpDir):
        lineList = []
        lineList2 = []
        with open("/etc/hosts", "r") as f:
            b = -1
            for line in f.read().rstrip("\n").split("\n"):
                if line == "### wrtd begin ###":
                    b = 0
                if b == -1:
                    lineList.append(line)
                if b == 1:
                    lineList2.append(line)
                if line == "### wrtd end ###":
                    b = 1

        lineList.append("### wrtd begin ###")
        for fn in glob.glob(os.path.join(tmpDir, "hosts.d", "*")):
            for ip, hostname in WrtUtil.readDnsmasqHostFile(fn):
                lineList.append("%s %s" % (ip, hostname))
        for r in WrtUtil.readDnsmasqLeaseFile(os.path.join(tmpDir, "dnsmasq.leases")):
            if r[2] == "":
                continue
            lineList.append("%s %s" % (r[1], r[2]))
        lineList.append("### wrtd end ###")

        lineList += lineList2
        while len(lineList) > 0 and lineList[-1] == "":
            del lineList[-1]

        with open("/etc/hosts", "w") as f:
            f.write("\n".join(lineList))
            f.write("\n")

    def getWanConnectionPluginList(param):
        return WrtCommon._getPluginList(param, "wconn")

    def getWanConnectionPlugin(param, name):
        ret = WrtCommon._getPlugin(param, "wconn", name)
        if ret is None:
            raise Exception("wan connection type plugin %s does not exists" % (name))
        return ret

    def getWanVpnPluginList(param):
        return WrtCommon._getPluginList(param, "wvpn")

    def getWanVpnPlugin(param, name):
        ret = WrtCommon._getPlugin(param, "wvpn", name)
        if ret is None:
            raise Exception("wan vpn plugin %s does not exists" % (name))
        return ret

    def getLanInterfacePluginList(param):
        return WrtCommon._getPluginList(param, "lif")

    def getLanInterfacePlugin(param, name):
        ret = WrtCommon._getPlugin(param, "lif", name)
        if ret is None:
            raise Exception("lan interface plugin %s does not exists" % (name))
        return ret

    def _getPluginList(param, prefix):
        ret = []
        for fn in glob.glob(os.path.join(param.libDir, "plugins", prefix + "_*")):
            modname = fn.replace("/", ".")
            exec("import %s" % (modname))
            ret += eval("%s.get_plugin_list()" % (modname))
        return ret

    def _getPlugin(param, prefix, name):
        for fn in glob.glob(os.path.join(param.libDir, "plugins", prefix + "_*")):
            modname = fn.replace("/", ".")
            exec("import %s" % (modname))
            if name in eval("%s.get_plugin_list()" % (modname)):
                return eval("%s.get_plugin(%s)" % (name))
        return None


class DnsMasqHostFilesLock:

    def __init__(self, tmpDir):
        self.lockFile = os.path.join(tmpDir, "hosts.d", ".lock")
        self.lockFd = None

    def __enter__(self):
        try:
            self.lockFd = os.open(self.lockFile, os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC, 0o600)
            fcntl.lockf(self.lockFd, fcntl.LOCK_EX)
        except:
            if self.lockFd is not None:
                os.close(self.lockFd)
                self.lockFd = None

    def __exit__(self, *_):
        os.close(self.lockFd)
        self.lockFd = None


"""
plugin module name: plugins.wconn_*
config file: ${ETC}/wan-connection.json
only allow one plugin be loaded
"""


class PluginTemplateWanConnection:

    def init2(self, tmpDir, ownResolvConf):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False


"""
plugin module name: plugins.wvpn_*
config file: ${ETC}/wan-vpn.json
only allow one plugin be loaded
"""


class PluginTemplateWanVpn:

    def init2(self, vpnIntf, tmpDir):
        assert False

    def start(self, cfg):
        assert False

    def stop(self):
        assert False

    def is_alive(self):
        assert False

    def get_local_ip(self):
        assert False

    def get_remote_ip(self):
        assert False

    def get_netmask(self):
        assert False


"""
plugin module name: plugins.lif_*
config file: ${ETC}/lan-interface-(PLUGIN_NAME)-(INSTANCE_NAME).json
allow multiple plugins be loaded, and one plugin can have multiple instances
"""


class _PluginObjectLanInterface:

    def init2(self, cfg):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def interface_appear(self, ifname):
        # return True means we take this interface
        pass

    def interface_disappear(self, ifname):
        pass
