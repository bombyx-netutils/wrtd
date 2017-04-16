#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
import fcntl


class WrtCommon:

    @staticmethod
    def getWanConnectionPluginList(param):
        return WrtCommon._getPluginList(param, "wconn")

    @staticmethod
    def getWanConnectionPlugin(param, name):
        ret = WrtCommon._getPlugin(param, "wconn", name)
        if ret is None:
            raise Exception("wan connection type plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def getWanVpnPluginList(param):
        return WrtCommon._getPluginList(param, "wvpn")

    @staticmethod
    def getWanVpnPlugin(param, name):
        ret = WrtCommon._getPlugin(param, "wvpn", name)
        if ret is None:
            raise Exception("wan vpn plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def getLanInterfacePluginList(param):
        return WrtCommon._getPluginList(param, "lif")

    @staticmethod
    def getLanInterfacePlugin(param, name):
        ret = WrtCommon._getPlugin(param, "lif", name)
        if ret is None:
            raise Exception("lan interface plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def _getPluginList(param, prefix):
        ret = []
        for fn in glob.glob(os.path.join(param.libDir, "plugins", prefix + "_*")):
            modname = fn
            modname = modname[len(param.libDir + "/"):]
            modname = modname.replace("/", ".")
            exec("import %s" % (modname))
            ret += eval("%s.get_plugin_list()" % (modname))
        return ret

    @staticmethod
    def _getPlugin(param, prefix, name):
        for fn in glob.glob(os.path.join(param.libDir, "plugins", prefix + "_*")):
            modname = fn
            modname = modname[len(param.libDir + "/"):]
            modname = modname.replace("/", ".")
            exec("import %s" % (modname))
            if name in eval("%s.get_plugin_list()" % (modname)):
                return eval("%s.get_plugin(\"%s\")" % (modname, name))
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


class TemplateBridge:

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_ip(self):
        assert False

    def get_netmask(self):
        assert False

    def get_subhost_ip_range(self):
        # return (start_ip, end_ip)
        assert False

    def on_bridge_created(self, ip):
        assert False

    def on_bridge_destroyed(self, ip):
        assert False

    def on_upstream_connected(self, ip):
        assert False

    def on_upstream_disconnected(self, ip):
        assert False

    def on_host_appear(self, ownerName, ipDataDict):
        assert False

    def on_host_disappear(self, ownerName, ipList):
        assert False

    def hosts_changed(self):
        assert False                # fixme

    def domain_nameserver_changed(self):
        assert False                # fixme




# plugin module name: plugins.wconn_*
# config file: ${ETC}/wan-connection.json
# only allow one plugin be loaded
class PluginTemplateWanConnection:

    def init2(self, tmpDir, ownResolvConf):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_out_interface(self):
        assert False

    def interface_appear(self, ifname):
        # return True means we take this interface
        # must be call after start()
        assert False

    def interface_disappear(self, ifname):
        # must be call after start()
        assert False


# plugin module name: plugins.wvpn_*
# config file: ${ETC}/wan-vpn.json
# only allow one plugin be loaded
class PluginTemplateWanVpn:

    def init2(self, tmpDir):
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

    def get_interface(self):
        assert False


# plugin module name: plugins.lif_*
# config file: ${ETC}/lan-interface-(PLUGIN_NAME)-(INSTANCE_NAME).json
# allow multiple plugins be loaded, and one plugin can have multiple instances
class TemplatePluginLanInterface:

    def init2(self, instanceName, cfg, brname, tmpDir):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_bridge(self):
        # return None means using default bridge
        # must be call after start()
        assert False

    def interface_appear(self, ifname):
        # return True means we take this interface
        # must be call after start()
        assert False

    def interface_disappear(self, ifname):
        # must be call after start()
        assert False
