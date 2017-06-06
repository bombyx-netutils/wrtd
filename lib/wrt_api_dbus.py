#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import json
import dbus
import dbus.service
from wrt_util import WrtUtil
from wrt_common import WrtCommon


################################################################################
# DBus API Docs
################################################################################
#
# ==== Main Application ====
# Service               org.fpemud.WRT
# Interface             org.fpemud.WRT
# Object path           /
#
# Methods:
# info:json                                    GetRouterInfo()
# (suggested_filename:str,content:str)         GenerateClientScript(lif_plugin_id:str, os_type:str)
#
class DbusMainObject(dbus.service.Object):

    def __init__(self, param):
        self.param = param

        # register dbus object path
        bus_name = dbus.service.BusName('org.fpemud.WRT', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/org/fpemud/WRT')

    def release(self):
        self.remove_from_connection()

    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='s')
    def GetRouterInfo(self):
        ret = dict()

        if self.param.wanManager.wanConnPlugin is not None:
            plugin = self.param.wanManager.wanConnPlugin
            ret["wconn-plugin"] = dict()
            ret["wconn-plugin"]["name"] = plugin.full_name
            if plugin.is_alive():
                ret["wconn-plugin"]["alive"] = True
                ret["wconn-plugin"]["ip"] = plugin.get_ip()
                ret["wconn-plugin"]["is-ip-public"] = WrtUtil.isIpPublic(plugin.get_ip())
            else:
                ret["wconn-plugin"]["alive"] = False

        if self.param.wanManager.vpnPlugin is not None:
            plugin = self.param.wanManager.vpnPlugin
            ret["wvpn-plugin"] = dict()
            ret["wvpn-plugin"]["name"] = plugin.full_name
            if plugin.is_alive():
                ret["wvpn-plugin"]["alive"] = True
            else:
                ret["wvpn-plugin"]["alive"] = False

        ret["default-bridge"] = dict()
        if True:
            ret["default-bridge"] = dict()
            ret["default-bridge"]["ip"] = WrtCommon.bridgeGetIp(self.param.lanManager.defaultBridge)
            ret["default-bridge"]["mask"] = self.param.lanManager.defaultBridge.get_prefix()[1]

        ret["lif-plugin"] = dict()
        for plugin in self.param.lanManager.lifPluginList:
            ret["lif-plugin"][plugin.full_name] = dict()

        ret["vpns-plugin"] = dict()
        for plugin in self.param.lanManager.vpnsPluginList:
            ret["vpns-plugin"][plugin.full_name] = dict()
            ret["vpns-plugin"][plugin.full_name]["bridge"] = dict()
            ret["vpns-plugin"][plugin.full_name]["bridge"]["name"] = plugin.get_bridge().get_name()
            ret["vpns-plugin"][plugin.full_name]["bridge"]["ip"] = WrtCommon.bridgeGetIp(plugin.get_bridge())
            ret["vpns-plugin"][plugin.full_name]["bridge"]["mask"] = plugin.get_bridge().get_prefix()[1]

        return json.dumps(ret)

    @dbus.service.method('org.fpemud.WRT', in_signature='ss', out_signature='ss')
    def GenerateClientScript(self, vpns_plugin_full_name, os_type):
        if os_type not in ["linux", "win32"]:
            raise Exception("Invalid OS type.")

        pluginObj = None
        for po in self.param.lanManager.vpnsPluginList:
            if po.full_name == vpns_plugin_full_name:
                pluginObj = po
                break
        if pluginObj is None:
            raise Exception("The specified plugin does not exist.")

        if not hasattr(pluginObj, "generate_client_script"):
            raise Exception("The specified plugin has no client script capability.")

        if self.param.wanManager.wanConnPlugin is None:
            raise Exception("No internet connection.")
        if not self.param.wanManager.wanConnPlugin.is_alive():
            raise Exception("No internet connection.")
        ip = self.param.wanManager.wanConnPlugin.get_ip()
        if not WrtUtil.isIpPublic(ip):
            raise Exception("Internet connection is behind NAT.")

        return pluginObj.generate_client_script(ip, os_type)


################################################################################
# DBus API Docs
################################################################################
#
# ==== Main Application ====
# Service               org.fpemud.IpForward
# Interface             org.fpemud.IpForward
# Object path           /
#
# Methods:
# void                  On()
# void                  Off()
#

class DbusIpForwardObject(dbus.service.Object):

    def __init__(self, param):
        # implement a fake IpForward object, since we always set ip_forward to 1
        bus_name = dbus.service.BusName('org.fpemud.IpForward', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/org/fpemud/IpForward')

    def release(self):
        self.remove_from_connection()

    @dbus.service.method('org.fpemud.IpForward')
    def On(self):
        pass

    @dbus.service.method('org.fpemud.IpForward')
    def Off(self):
        pass
