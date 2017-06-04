#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import dbus
import dbus.service
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
# str                                          GetWanConnInfo()
# (suggested_filename:str,content:str)         GenerateClientScript(lif_plugin_id:str, os_type:str)
# (mac,ip,hostname)                            GetClients()


# str                                          GetIp()
# int                                          GetMask()
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
    def GetWanConnInfo(self):
        if self.param.wanManager.wanConnPlugin is None:
            return "None"

        plugin = self.param.wanManager.wanConnPlugin
        msg = ""
        msg += "Plugin: " + plugin.plugin_id + "\n"
        msg += "Status: " + ("Connected" if plugin.is_alive() else "Disconnected")
        return msg

    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='s')
    def GetLanInterfaceInfo(self):
        msg = "\n".join(x.plugin_id for x in self.param.lanManager.get_plugins())
        return msg

    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='s')
    def GetIp(self):
        if self.param.lanManager is None:
            return None
        else:
            return WrtCommon.bridgeGetIp(self.param.lanManager.defaultBridge)

    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='s')
    def GetMask(self):
        if self.param.lanManager is None:
            return None
        else:
            return self.param.lanManager.defaultBridge.get_mask()

#    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='a(sssb)')
    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='a(s)')
    def GetClients(self):
        return self.param.lanManager.get_clients()

    @dbus.service.method('org.fpemud.WRT', in_signature='ss', out_signature='ss')
    def GenerateClientScript(self, lif_plugin_id, os_type):
        if os_type not in ["linux", "win32"]:
            raise Exception("invalid OS type")

        pluginObj = None
        for po in self.param.lanManager.get_plugins():
            if po.plugin_id == lif_plugin_id:
                pluginObj = po
                break
        if pluginObj is None:
            raise Exception("the specified plugin does not exist")

        if not hasattr(pluginObj, "generate_client_script"):
            raise Exception("the specified plugin has no client script capability")
        if os_type not in ["linux", "win32"]:
            raise Exception("invalid OS type")
        return pluginObj.generate_client_script(os_type)


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
