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
        msg += "Status: " + "Connected" if plugin.is_alive() else "Disconnected"
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
