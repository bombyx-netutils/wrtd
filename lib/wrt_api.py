#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
import json
import time
import dbus
import queue
import socket
import logging
import threading
import dbus.service
from gi.repository import GLib
from wrt_util import WrtUtil


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
# str                                          GetIp()
# int                                          GetMask()
# (mac,ip,hostname,bWiredOrWireless)           GetClients()
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
    def GetIp(self):
        return self.param.ip

    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='s')
    def GetMask(self):
        return self.param.mask

    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='a(sssb)')
    def GetClients(self):
        return []
        # ret = []
        # for c in self.param.lanManager.getClients():
        #     ret.append((c.mac, c.ip, c.hostname, c.bWiredOrWireless))
        # return ret


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


################################################################################
# Command: get-host-list
################################################################################
#
# Request:
# {
#     "command": "get-host-list",
# }
# Response:
# {
#     "return": {
#         "1.2.3.4": {
#             "hostname": "abcd",
#             "wakeup-mac": "01-02-03-04-05-06",
#         },
#     },
# }
#
################################################################################
# Notify: host-appear
################################################################################
#
# {
#     "notify": "host-appear",
#     "data": {
#         "1.2.3.4": {
#             "hostname": "abcd",
#             "wakeup-mac": "01-02-03-04-05-06",
#         },
#     },
# }
#
################################################################################
# Notify: host-change
################################################################################
#
# {
#     "notify": "host-change",
#     "data": {
#         "1.2.3.4": {
#             "hostname": "abcd",
#             "wakeup-mac": "01-02-03-04-05-06",
#         },
#     },
# }
#
################################################################################
# Notify: host-disappear
################################################################################
#
# {
#     "notify": "host-disappear",
#     "data": [
#         "1.2.3.4",
#     ],
# }
#
################################################################################
# Command: register-subhost-owner
################################################################################
#
# Request:
# {
#     "command": "register-subhost-owner",
# }
# Response:
# {
#     "return": {
#         "start": "192.168.1.100",
#         "end": "192.168.1.200",
#     },
# }
#
################################################################################
# Command: add-subhost
################################################################################
#
# Request:
# {
#     "command": "add-subhost",
#     "data": {
#         "1.2.3.4": {
#             "hostname": "abcd",
#             "wakeup-mac": "01-02-03-04-05-06",
#         },
#     }
# }
# Response:
# {
#     "return": {
#     },
# }
#
################################################################################
# Command: remove-subhost
################################################################################
#
# Request:
# {
#     "command": "remove-subhost",
#     "data": [
#         "1.2.3.4",
#     ]
# }
# Response:
# {
#     "return": {
#     },
# }
#
################################################################################
# Command: wakeup-host
################################################################################
#
# Request:
# {
#     "command": "wakeup-host",
#     "data": {
#         "mac": "01-02-03-04-05-06",
#     },
# }
# Response:
# {
#     "return": {
#     },
# }
#

class WrtApiServer:

    def __init__(self, param):
        self.param = param
        self.subhostOwnerDict = dict()

        self.realServer = JsonApiServer()
        self.realServer.addCommand("get-host-list", self._cmdGetHostList)
        self.realServer.addCommand("register-subhost-owner", self._cmdRegisterSubhostOwner)
        self.realServer.addCommand("add-subhost", self._addSubhost)
        self.realServer.addCommand("remove-subhost", self._removeSubhost)
        self.realServer.addCommand("wakeup-host", self._cmdWakeupHost)
        self.realServer.addNotify("host-appear")
        self.realServer.addNotify("host-disappear")

    def dispose(self):
        self.realServer.dispose()

    def addClientIp(self, ip):
        self.realServer.addClientIp(ip)

    def removeClientIp(self, ip):
        self.realServer.removeClientIp(ip)

    def notifyAppear(self, ip, hostname, wakeupMac):
        ipDataDict = dict()
        ipDataDict[ip] = dict()
        if hostname is not None:
            ipDataDict[ip]["hostname"] = hostname
        if wakeupMac is not None:
            ipDataDict[ip]["wakeup-mac"] = wakeupMac
        self.realServer.sendNotify("host-appear", ipDataDict)

    def notifyDisappear(self, ip):
        ipList = [ip]
        self.realServer.sendNotify("host-disappear", ipList)

    def notifyAppear2(self, ipDataDict):
        self.realServer.sendNotify("host-appear", ipDataDict)

    def notifyDisappear2(self, ipList):
        self.realServer.sendNotify("host-disappear", ipList)

    def _cmdGetHostList(self):
        dataDict = dict()
        for fn in glob.glob(os.path.join(self.param.tmpDir, "hosts.d", "*")):
            for ip, hostname in WrtUtil.readDnsmasqHostFile(fn):
                dataDict[ip] = {"hostname": hostname}
        for r in WrtUtil.readDnsmasqLeaseFile(os.path.join(self.param.tmpDir, "dnsmasq.leases")):
            ip = r[1]
            dataDict[ip] = {"mac": r[0]}
            if r[2] != "":
                dataDict[ip]["hostname"] = r[2]

        with self.sendLock:
            self.sock.send(json.dumps({
                "return": dataDict,
            }).encode("utf-8"))

    def _cmdRegisterSubhostOwner(self):
        # validate source ip
        if self.addr not in self.param.lanManager.get_clients():
            throw Exception("invalid source address")

        # add subhost-owner
        with self.pObj.globalLock:
            if self.sock in self.pObj.subhostOwnerDict:
                # delete subhost file  --fixme
                start = self.pObj.subhostOwnerDict[self.sock]
            else:
                start = None
                for s in range(self.param.subHostRangeStart, self.param.subHostRangeEnd + 1, self.param.subHostBlockSize):
                    if s in self.pObj.subhostOwnerDict.values():
                        continue
                    start = s
                    break
                if start is None:
                    self.sock.send(json.dumps({
                        "result": "error",
                        "error": "too many sub-host owners",
                    }).encode("utf-8"))
                    return
            self.pObj.subhostOwnerDict[self.sock] = start

        # send response
        ipstart = ".".join(self.addr.split(".")[:-1] + [str(start)])
        ipend = ".".join(self.addr.split(".")[:-1] + [str(start + self.param.subHostBlockSize)])
        self.sock.send(json.dumps({
            "result": "success",
            "start": ipstart,
            "end": ipend,
        }).encode("utf-8"))

    def _addSubhost(self, jsonObj):
        # check
        if self.sock not in self.pObj.subhostOwnerDict:
            self.sock.send(json.dumps({
                "result": "error",
                "error": "invalid source address",
            }).encode("utf-8"))
            return

    def _removeSubhost(self, jsonObj):
        pass

    def _cmdWakeupHost(self, mac):
        WrtUtil.shell("/usr/bin/wakeonlan -i %s %s" % (self.param.baddr, mac))

        with self.sendLock:
            self.sock.send(json.dumps({
                "return": {},
            }).encode("utf-8"))


class WrtApiClient:

    def __init__(self, ip, port):
        self.realClient = JsonApiClient(ip, port)
        self.realClient.registerNotifyCallback("host-appear", self._notifyHostAppear)
        self.realClient.registerNotifyCallback("host-disappear", self._notifyHostDisappear)

    def dispose(self):
        self.realClient.dispose()

    def registerSubhostOwner(self):
        self.realClient.execCommand("register-subhost-owner")

    def addSubhost(self, ipDataDict):
        self.realClient.execCommand("add-subhost", ipDataDict)

    def removeSubhost(self, ipList):
        self.realClient.execCommand("remove-subhost", ipList)

    def _notifyHostAppear(self, data):
        pass

    def _notifyHostDisappear(self, data):
        pass