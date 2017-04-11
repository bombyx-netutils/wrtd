#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
import json
import time
import queue
import socket
import logging
import threading
from gi.repository import GLib
from wrt_util import WrtUtil


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

class WrtApiServer:

    def __init__(self, param):
        self.param = param

        self.servSockList = []
        for ip in ["127.0.0.1", self.param.ip]:
            serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serverSock.bind((ip, self.param.sgwApiPort))
            serverSock.listen(5)
            serverSock.setblocking(0)
            serverSourceId = GLib.io_add_watch(serverSock, GLib.IO_IN | _flagError, self._onServerAccept)
            self.servSockList.append((serverSock, serverSourceId))

        self.threadDict = dict()
        self.threadDictLock = threading.Lock()

    def dispose(self):
        for serverSock, serverSourceId in self.servSockList:
            GLib.source_remove(serverSourceId)
            serverSock.close()
        self.servSockList = []

        with self.threadDictLock:
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
            with self.threadDictLock:
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

        with self.threadDictLock:
            for tRecv, tSend in self.threadDict:
                if tSend is not None:
                    tSend.queue.put(jsonObj)

    def notifyDisappear(self, ip):
        jsonObj = dict()
        jsonObj["notify"] = "host-disappear"
        jsonObj["data"] = [ip]

        with self.threadDictLock:
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
                    logging.info("Process SGW command \"%s\" from \"%s\"", jsonObj["command"], self.addr)
                except Exception as e:
                    logging.error("Failed to process SGW command from %s, %s", self.addr, e)
                    logging.debug("_CommandThread.run: Exception, %s, %s", e.__class__, e)
        finally:
            _disposeClient(self.pObj, self.sock, 0)

    def _processCommand(self, jsonObj):
        if "command" not in jsonObj:
            raise Exception("invalid command")

        if jsonObj["command"] == "get-host-list":
            self._cmdGetHostList()
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
                    logging.info("Send SGW notify \"%s\" to \"%s\"", jsonObj["notify"], self.addr)
                except Exception as e:
                    logging.error("Failed to send SGW notify to %s, %s", self.addr, e)
                    logging.debug("_NotifyThread.run: Exception, %s, %s", e.__class__, e)
                finally:
                    self.queue.task_done()
        finally:
            _disposeClient(self.pObj, self.sock, 1)


def _disposeClient(pobj, sock, elem_id):
    with pobj.threadDictLock:
        pobj.threadDict[sock][elem_id] = None
        if all(x is None for x in pobj.threadDict[sock]):
            del pobj.threadDict[sock]
            sock.close()


_flagError = GLib.IO_PRI | GLib.IO_ERR | GLib.IO_HUP | GLib.IO_NVAL
