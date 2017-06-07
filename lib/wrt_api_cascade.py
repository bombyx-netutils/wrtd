#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import threading
from wrt_util import JsonApiServer
from wrt_util import JsonApiClient
from wrt_common import WrtCommon


################################################################################
# Command: register
################################################################################
#
# Request:
# {
#     "command": "register",
#     "data": {
#         "router-id": "c5facfa6-d8c3-4bce-ac13-6abab49c86fc",
#     },
# }
# Response:
# {
#     "return": {
#         "router-id": "c5facfa6-d8c3-4bce-ac13-6abab49c86fc",
#         "subhost-start": "192.168.1.100",
#         "subhost-end": "192.168.1.200",
#     },
# }
#
################################################################################
# Command: change-wan-prefix-list
################################################################################
#
# Request:
# {
#     "command": "change-wan-prefix-list",
#     "data": [
#         "192.168.2.0/255.255.255.0",
#         "192.168.1.0/255.255.255.0",
#     ]
# }
# Response:
# {
#     "return": {
#     },
# }
#
################################################################################
# Command: change-lan-prefix-list
################################################################################
#
# Request:
# {
#     "command": "change-lan-prefix-list",
#     "data": [
#         "192.168.2.0/255.255.255.0",
#         "192.168.1.0/255.255.255.0",
#     ]
# }
# Response:
# {
#     "return": {
#     },
# }
#
################################################################################
# Command: new-or-change-client
################################################################################
#
# Request:
# {
#     "command": "new-or-change-client",
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
# Command: delete-client
################################################################################
#
# Request:
# {
#     "command": "delete-client",
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
# Command: new-router
################################################################################
#
# Request:
# {
#     "command": "new-router",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc": {
#             "parent": "c6f7cdad-d2ce-3478-cabc-a3b5445bdfee",
#             "wan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#             "lan-prefix-list": ["192.168.2.0/255.255.255.0", "192.168.3.0/255.255.255.0"],
#             "client-list": {
#                 "1.2.3.4": {
#                     "hostname": "abcd",
#                     "wakeup-mac": "01-02-03-04-05-06",
#                 },
#             },
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
# Command: delete-router
################################################################################
#
# Request:
# {
#     "command": "delete-router",
#     "data": [
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc",
#     ],
# }
# Response:
# {
#     "return": {
#     },
# }
#
################################################################################
# Notify: change-router-wan-prefix-list
################################################################################
#
# Request:
# {
#     "command": "change-router-wan-prefix-list",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "wan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#         }
#     },
# }
# Response:
# {
#     "return": {
#     },
# }
#
################################################################################
# Notify: change-router-lan-prefix-list
################################################################################
#
# Request:
# {
#     "command": "change-router-lan-prefix-list",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "lan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#         }
#     },
# }
# Response:
# {
#     "return": {
#     },
# }
#
################################################################################
# Notify: add-or-change-router-client
################################################################################
#
# Request:
# {
#     "command": "add-or-change-router-client",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "client-list": {
#                 "1.2.3.4": {
#                     "nat-ip": "2.3.4.5",
#                     "hostname": "abcd",
#                     "wakeup-mac": "01-02-03-04-05-06",
#                 },
#             },
#         ],
#     },
# }
# Response:
# {
#     "return": {
#     },
# }
#
################################################################################
# Notify: remove-router-client
################################################################################
#
# Request:
# {
#     "notify": "remove-router-client",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "client-list": [
#                 "1.2.3.4",
#             ],
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
# Notify: router-add
################################################################################
#
# {
#     "notify": "router-add",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc": {
#             "parent": "c6f7cdad-d2ce-3478-cabc-a3b5445bdfee",
#             "wan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#             "lan-prefix-list": ["192.168.2.0/255.255.255.0", "192.168.3.0/255.255.255.0"],
#             "client-list": {
#                 "1.2.3.4": {
#                     "hostname": "abcd",
#                     "wakeup-mac": "01-02-03-04-05-06",
#                 },
#             },
#         },
#     },
# }
#
################################################################################
# Notify: router-remove
################################################################################
#
# {
#     "notify": "router-remove",
#     "data": [
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc",
#     ],
# }
#
################################################################################
# Notify: router-wan-prefix-list-change
################################################################################
#
# {
#     "notify": "router-wan-prefix-list-change",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "wan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#         }
#     },
# }
#
################################################################################
# Notify: router-lan-prefix-list-change
################################################################################
#
# {
#     "notify": "router-lan-prefix-list-change",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "lan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#         }
#     },
# }
#
################################################################################
# Notify: router-client-add-or-change
################################################################################
#
# {
#     "notify": "router-client-add-or-change",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "client-list": {
#                 "1.2.3.4": {
#                     "nat-ip": "2.3.4.5",
#                     "hostname": "abcd",
#                     "wakeup-mac": "01-02-03-04-05-06",
#                 },
#             },
#         ],
#     },
# }
#
################################################################################
# Notify: router-client-remove
################################################################################
#
# {
#     "notify": "router-client-remove",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "client-list": [
#                 "1.2.3.4",
#             ],
#         },
#     },
# }
#


class WrtCascadeApiServer:

    def __init__(self, param, bridge):
        self.param = param
        self.bridge = bridge

        self.globalLock = threading.Lock()
        self.freeIpRange = self.bridge.get_subhost_ip_range()
        self.subhostOwnerDict = dict()

        self.realServer = JsonApiServer([WrtCommon.bridgeGetIp(bridge)], self.param.cascadeApiPort)

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

    def notifyUpstreamRefresh(self, upstreamDict):
        self.realServer.sendNotify("upstream-refresh", upstreamDict)

    def notifyHostRefresh(self, ipDataDict):
        self.realServer.sendNotify("host-refresh", ipDataDict)

    def _clientInitCallback(self, addr):
        # upstream info

        # host info

        # subhost ip range
        with self.globalLock:
            if len(self.freeIpRange) == 0:
                raise Exception("too many sub-host owners")
            self.subhostOwnerDict[addr] = _WrtSubhostOwnerData()
            self.subhostOwnerDict[addr].ipRange = self.freeIpRange.pop(0)

        self.bridge.on_subhost_owner_connected(self._source_id(addr))

        # return value
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
        for bridge in WrtCommon.getAllBridges(self.param):
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
        for bridge in WrtCommon.getAllBridges(self.param):
            if bridge == self.bridge:
                continue
            bridge.on_host_disappear(self.bridge.get_bridge_id(), ipList)

    def _prefixConflict(self, prefixList):
        pass

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

    def prefixConflict(self, prefixList):
        self.realClient.execCommand("prefix-conflict", prefixList)

    def _notifyHostRefresh(self, ipDataDict):
        # notify all bridges
        for bridge in WrtCommon.getAllBridges(self.param):
            bridge.on_host_refresh(self.upstreamId, ipDataDict)

        # notify subhost owners
        for s in self.param.cascadeApiServerList:
            # fixme
            s.notifyHostRefresh(ipDataDict)


class _WrtSubhostOwnerData:

    def __init__(self):
        self.ipRange = []
        self.ipDataDict = dict()
