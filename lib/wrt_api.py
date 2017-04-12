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

        self.serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSock.bind(("0.0.0.0", self.param.apiPort))
        self.serverSock.listen(5)
        self.serverSock.setblocking(0)
        self.serverSourceId = GLib.io_add_watch(self.serverSock, GLib.IO_IN | _flagError, self._onServerAccept)

        self.globalLock = threading.Lock()
        self.threadDict = dict()
        self.subhostOwnerDict = dict()

    def dispose(self):
        GLib.source_remove(self.serverSourceId)
        self.serverSock.close()

        with self.globalLock:
            for tRecv, tSend in self.threadDict:
                if tRecv is not None:
                    tRecv.sock.shutdown(socket.SHUT_WR)
                if tSend is not None:
                    tSend.bStop = True
        while len(self.threadDict) > 0:
            time.sleep(1.0)

    def _onServerAccept(self, source, cb_condition):
        assert not (cb_condition & _flagError)

        try:
            new_sock, addr = source.accept()
            with self.globalLock:
                sendLock = threading.Lock()
                tRecv = _CommandThread(self, new_sock, addr[0], sendLock)
                tSend = _NotifyThread(self, new_sock, addr[0], sendLock)
                self.threadDict[new_sock] = (tRecv, tSend)
                tRecv.start()
                tSend.Start()
            return True
        except socket.error as e:
            logging.debug("WrtApiServer._onServerAccept: Failed, %s, %s", e.__class__, e)
            return True

    def notifyAppear(self, ip, hostname, wakeupMac):
        jsonObj = dict()
        jsonObj["notify"] = "host-appear"
        jsonObj["data"] = dict()
        jsonObj["data"][ip] = dict()
        if hostname is not None:
            jsonObj["data"][ip]["hostname"] = hostname
        if wakeupMac is not None:
            jsonObj["data"][ip]["wakeup-mac"] = wakeupMac

        with self.globalLock:
            for tRecv, tSend in self.threadDict:
                if tSend is not None:
                    tSend.queue.put(jsonObj)

    def notifyDisappear(self, ip):
        jsonObj = dict()
        jsonObj["notify"] = "host-disappear"
        jsonObj["data"] = [ip]

        with self.globalLock:
            for tRecv, tSend in self.threadDict:
                if tSend is not None:
                    tSend.queue.put(jsonObj)


class _CommandThread(threading.Thread):

    def __init__(self, pObj, sock, addr, sendLock):
        threading.Thread.__init__(self)
        self.pObj = pObj
        self.sock = sock
        self.addr = addr
        self.sendLock = sendLock

    def run(self):
        try:
            while True:
                buf = WrtUtil.recvLine(self.sock).decode("utf-8")
                if len(buf) == 0:
                    break
                try:
                    jsonObj = json.loads(buf)
                    self._processCommand(jsonObj)
                    logging.info("Process API command \"%s\" from \"%s\"", jsonObj["command"], self.addr)
                except Exception as e:
                    logging.error("Failed to process API command from %s, %s", self.addr, e)
                    logging.debug("_CommandThread.run: Exception, %s, %s", e.__class__, e)
        finally:
            _disposeClient(self.pObj, self.sock, 0)

    def _processCommand(self, jsonObj):
        if "command" not in jsonObj:
            raise Exception("invalid command")

        if jsonObj["command"] == "get-host-list":
            self._cmdGetHostList()
        elif jsonObj["command"] == "register-subhost-owner":
            self._registerSubhostOwner()
        elif jsonObj["command"] == "add-subhost":
            self._addSubhost(jsonObj["data"])
        elif jsonObj["command"] == "remove-subhost":
            self._removeSubhost(jsonObj["data"])
        elif jsonObj["command"] == "wakeup-host":
            self._cmdWakeupHost(jsonObj["data"])
        else:
            raise Exception("invalid command \"%s\"" % (jsonObj["command"]))

    def _cmdGetHostList(self, ostype):
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

    def _cmdRegisterSubhostOwner(self, jsonObj):
        # validate source ip
        found = False
        for r in WrtUtil.readDnsmasqLeaseFile(os.path.join(self.param.tmpDir, "dnsmasq.leases")):
            if r[1] == self.addr:
                found = True
                break
        if not found:
            self.sock.send(json.dumps({
                "result": "error",
                "error": "invalid source address",
            }).encode("utf-8"))
            return

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

    def _updateSubhost(self, jsonObj):
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


class _NotifyThread(threading.Thread):

    def __init__(self, pObj, sock, addr, sendLock):
        threading.Thread.__init__(self)
        self.pObj = pObj
        self.sock = sock
        self.addr = addr
        self.sendLock = sendLock
        self.queue = queue.queue()
        self.bStop = False

    def run(self):
        try:
            while True:
                if self.bStop:
                    break
                try:
                    jsonObj = self.queue.get(timeout=10)
                except queue.Empty:
                    continue

                if self.bStop:
                    break
                try:
                    buf = json.dumps(jsonObj)
                    with self.sendLock:
                        self.sock.send(buf)
                    logging.info("Send notify \"%s\" to \"%s\"", jsonObj["notify"], self.addr)
                except Exception as e:
                    logging.error("Failed to send notify to %s, %s", self.addr, e)
                    logging.debug("_NotifyThread.run: Exception, %s, %s", e.__class__, e)
                finally:
                    self.queue.task_done()
        finally:
            _disposeClient(self.pObj, self.sock, 1)


def _disposeClient(pobj, sock, elem_id):
    with pobj.globalLock:
        pobj.threadDict[sock][elem_id] = None
        if all(x is None for x in pobj.threadDict[sock]):
            del pobj.threadDict[sock]
            sock.close()


class WrtApiClient:

    def __init__(self, ip, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((remoteIp, port))
            self.sock.send(json.dumps({
                "command": ""register-subhost-owner",
            }).encode("utf-8"))
            buf = WrtUtil.recvLine(sock).decode("utf-8")
            jsonObj = json.loads(buf)
            if jsonObj["result"] == "error":
                raise Exception(jsonObj["error"])
            for i in range(0, jsonObj["count"]):
                t = self.vpnPlugin.get_remote_ip().split(".")
                t[3] = str(jsonObj["start"] + i)
                self.subHostDict[".".join(t)] = None
        finally:
            sock.close()



_flagError = GLib.IO_PRI | GLib.IO_ERR | GLib.IO_HUP | GLib.IO_NVAL
