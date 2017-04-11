#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob


class WrtPluginManager:

    def __init__(self, param):
        self.param = param

    def getWanConnectionPluginList(self):
        return self._getPluginList("wan_conn")

    def getWanConnectionPlugin(self, name):
        ret = self._getPlugin("wan_conn", name)
        if ret is None:
            raise Exception("wan connection plugin %s does not exists" % (name))
        return ret

    def getVpnPluginList(self):
        return self._getPluginList("vpn")

    def getVpnPlugin(self, name):
        ret = self._getPlugin("vpn", name)
        if ret is None:
            raise Exception("VPN plugin %s does not exists" % (name))
        return ret

    def _getPluginList(self, prefix):
        ret = []
        for fn in glob.glob(os.path.join(self.param.libDir, "plugins", prefix + "_*")):
            modname = fn.replace("/", ".")
            exec("import %s" % (modname))
            ret += eval("%s.get_plugin_list()" % (modname))
        return ret

    def _getPlugin(self, prefix, name):
        for fn in glob.glob(os.path.join(self.param.libDir, "plugins", prefix + "_*")):
            modname = fn.replace("/", ".")
            exec("import %s" % (modname))
            if name in eval("%s.get_plugin_list()" % (modname)):
                return eval("%s.get_plugin(%s)" % (name))
        return None


class TemplateWanConnection:

    """
    module name: plugins.wan_conn_*
    """

    def start(self, cfg):
        assert False

    def stop(self):
        assert False


class TemplateVpn:

    """
    module name: plugins.vpn_*
    """

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
