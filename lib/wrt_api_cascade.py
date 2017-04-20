#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import threading
from wrt_util import JsonApiServer
from wrt_util import JsonApiClient


################################################################################
# Init
################################################################################
#
# {
#     "init": {
#         "upstream-ip-list": [
#             "1.1.1.1",
#             "1.2.3.4",
#         ]
#         "subhost-start": "192.168.1.100",
#         "subhost-end": "192.168.1.200",
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
#     },
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
# Notify: host-refresh
################################################################################
#
# {
#     "notify": "hosts-refresh",
#     "data": {
#         "1.2.3.4": {
#             "hostname": "abcd",
#             "wakeup-mac": "01-02-03-04-05-06",
#         },
#     },
# }
#
# Note: Hosts belong to myself is excluded.
#

class WrtCascadeApiServer:

    def __init__(self, param, bridge):
        self.param = param
        self.bridge = bridge

        self.globalLock = threading.Lock()
        self.freeIpRange = self.bridge.get_subhost_ip_range()
        self.subhostOwnerDict = dict()

        self.realServer = JsonApiServer([bridge.get_ip()], self.param.cascadeApiPort)

        self.realServer.setValidClient(True)
        self.realServer.setOneClientPerIp(True)

        self.realServer.setClientInitCallback(self._clientInitCallback)
        self.realServer.setClientTerminateCallback(self._clientTerminateCallback)

        self.realServer.addCommand("add-subhost", self._addSubhost)
        self.realServer.addCommand("remove-subhost", self._removeSubhost)

        self.realServer.addNotify("host-refresh")

    def dispose(self):
        self.realServer.dispose()

    def addValidClientIp(self, ip):
        self.realServer.addValidClientIp(ip)

    def removeValidClientIp(self, ip):
        self.realServer.removeValidClientIp(ip)

    def notifyHostRefresh(self, ipDataDict):
        self.realServer.sendNotify("host-refresh", ipDataDict)

    def _clientInitCallback(self, addr):
        with self.globalLock:
            if len(self.freeIpRange) == 0:
                raise Exception("too many sub-host owners")
            self.subhostOwnerDict[addr] = _WrtSubhostOwnerData()
            self.subhostOwnerDict[addr].ipRange = self.freeIpRange.pop(0)

        self.bridge.on_subhost_owner_connected(self._source_id(addr))

        return {
            "subhost-start": self.subhostOwnerDict[addr].ipRange[0],
            "subhost-end": self.subhostOwnerDict[addr].ipRange[1],
        }

    def _clientTerminateCallback(self, addr):
        self.bridge.on_subhost_owner_disconnected(self._source_id(addr))

        with self.globalLock:
            self.freeIpRange.append(self.subhostOwnerDict[addr].ipRange)
            del self.subhostOwnerDict[addr]

    def _addSubhost(self, addr, ipDataDict):
        # record
        for ip, data in ipDataDict:
            self.subhostOwnerDict[addr].ipDataDict[ip] = data

        # notify my bridge
        self.bridge.on_host_appear(self._source_id(addr), ipDataDict)

        # notify other bridges
        for bridge in self.param.lanManager.get_bridges():
            if bridge == self.bridge:
                continue
            bridge.on_host_appear(self.bridge.get_bridge_id(), ipDataDict)

    def _removeSubhost(self, addr, ipList):
        # record
        for ip in ipList:
            del self.subhostOwnerDict[addr].ipDataDict[ip]

        # notify my bridge
        self.bridge.on_host_disappear(self._source_id(addr), ipList)

        # notify other bridges
        for bridge in self.param.lanManager.get_bridges():
            if bridge == self.bridge:
                continue
            bridge.on_host_disappear(self.bridge.get_bridge_id(), ipList)

    def _source_id(self, addr):
        return "subhost-%s" % (addr[0])


class WrtCascadeApiClient:

    def __init__(self, param, ip, port):
        self.param = param
        self.realClient = JsonApiClient(ip, port)
        self.realClient.registerNotifyCallback("host-refresh", self._notifyHostRefresh)
        self.upstreamId = "upstream-%s" % (self.realClient.get_server_ip())

    def connect(self):
        return self.realClient.connect(bHasInit=True)

    def dispose(self):
        self.realClient.dispose()

    def addSubhost(self, ipDataDict):
        self.realClient.execCommand("add-subhost", ipDataDict)

    def removeSubhost(self, ipList):
        self.realClient.execCommand("remove-subhost", ipList)

    def _notifyHostRefresh(self, ipDataDict):
        # notify all bridges
        for bridge in self.param.lanManager.get_bridges():
            bridge.on_host_refresh(self.upstreamId, ipDataDict)

        # notify subhost owners
        for s in self.param.cascadeApiServerList:
            # fixme
            s.notifyHostRefresh(ipDataDict)


class _WrtSubhostOwnerData:

    def __init__(self):
        self.ipRange = []
        self.ipDataDict = dict()
