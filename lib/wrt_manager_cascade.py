#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import threading
from wrt_util import JsonApiServer
from wrt_util import JsonApiClient
from wrt_common import WrtCommon


################################################################################
# client2server: command: register
################################################################################
#
# Request:
# {
#     "command": "register",
#     "data": {
#         "my-id": "c5facfa6-d8c3-4bce-ac13-6abab49c86fc",
#         "router-list": {
#             "c5facfa6-d8c3-4bce-ac13-6abab49c86fc": {
#                 "parent": "c6f7cdad-d2ce-3478-cabc-a3b5445bdfee",
#                 "wan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#                 "lan-prefix-list": ["192.168.2.0/255.255.255.0", "192.168.3.0/255.255.255.0"],
#                 "client-list": {
#                     "1.2.3.4": {
#                         "hostname": "abcd",
#                         "wakeup-mac": "01-02-03-04-05-06",
#                     },
#                 },
#             },
#         },
#     },
# }
# Response:
# {
#     "return": {
#         "my-id": "c5facfa6-d8c3-4bce-ac13-6abab49c86fc",
#         "subhost-start": "192.168.1.100",
#         "subhost-end": "192.168.1.200",
#         "router-list": {
#             "c5facfa6-d8c3-4bce-ac13-6abab49c86fc": {
#                 "parent": "c6f7cdad-d2ce-3478-cabc-a3b5445bdfee",
#                 "wan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#                 "lan-prefix-list": ["192.168.2.0/255.255.255.0", "192.168.3.0/255.255.255.0"],
#                 "client-list": {
#                     "1.2.3.4": {
#                         "hostname": "abcd",
#                         "wakeup-mac": "01-02-03-04-05-06",
#                     },
#                 },
#             },
#         },
#     },
# }
#
################################################################################
# client2server: notification: new-router
################################################################################
#
# {
#     "notification": "new-router",
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
# client2server: notification: delete-router
################################################################################
#
# {
#     "notification": "delete-router",
#     "data": [
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc",
#     ],
# }
#
################################################################################
# client2server: notification: update-router-wan-prefix-list
################################################################################
#
# {
#     "notification": "update-router-wan-prefix-list",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "wan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#         }
#     },
# }
#
################################################################################
# client2server: notification: update-router-lan-prefix-list
################################################################################
#
# {
#     "notification": "update-router-lan-prefix-list",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "lan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#         }
#     },
# }
#
################################################################################
# client2server: notification: new-or-update-router-client
################################################################################
#
# {
#     "notification": "new-or-update-router-client",
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
# client2server: notification: delete-router-client
################################################################################
#
# {
#     "notification": "delete-router-client",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "client-list": [
#                 "1.2.3.4",
#             ],
#         },
#     },
# }
#
################################################################################
# server2client: notification: router-add
################################################################################
#
# {
#     "notification": "router-add",
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
# server2client: notification: router-remove
################################################################################
#
# {
#     "notification": "router-remove",
#     "data": [
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc",
#     ],
# }
#
################################################################################
# server2client: notification: router-wan-prefix-list-change
################################################################################
#
# {
#     "notification": "router-wan-prefix-list-change",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "wan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#         }
#     },
# }
#
################################################################################
# server2client: notification: router-lan-prefix-list-change
################################################################################
#
# {
#     "notification": "router-lan-prefix-list-change",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "lan-prefix-list": ["192.168.0.0/255.255.255.0", "192.168.1.0/255.255.255.0"],
#         }
#     },
# }
#
################################################################################
# server2client: notification: router-client-add-or-change
################################################################################
#
# {
#     "notification": "router-client-add-or-change",
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
# server2client: notification: router-client-remove
################################################################################
#
# {
#     "notification": "router-client-remove",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "client-list": [
#                 "1.2.3.4",
#             ],
#         },
#     },
# }
#


class WrtCascadeManager:

    def __init__(self, param):
        self.param = param

        # router info
        self.routerInfo = dict()
        self.routerInfo[self.param.uuid] = dict()
        self.routerInfo[self.param.uuid]["wan-prefix-list"] = []
        self.routerInfo[self.param.uuid]["lan-prefix-list"] = []
        self.routerInfo[self.param.uuid]["client-list"] = dict()

        # client api
        self.apiClient = None
        self.upstreamUuid = None
        self.upstreamRouterInfo = None

        # server api
        self.apiServerList = []
        self.routerInfoDownstream = dict()          # dict<api-server, router-json>

    def startApiClient(self, remote_ip):
        # exception in any callback function would make WrtCascadeManager bring down the cascade api client.
        # no exception is allowed in apiClientErrorCallback().
        # apiClientErrorCallback() would be called if there's error in cascade-api connection after startApiClient() returns.
        # apiClient is disposed before apiClientErrorCallback() is called.
        # no callback function should be called after the client calls disposeApiClient().

        logging.info("Establishing Cascade API connection.")

        self.apiClient = _ApiClient(self, remote_ip)
        self.apiClient.connect(remoet_ip, self.param.cascadeApiPort)

    def disposeApiClient(self):
        self.upstreamRouterInfo = None
        self.upstreamUuid = None
        if self.apiClient is not None:
            self.apiClient.dispose()
            self.apiClient = None

    def startApiServer(self, bridge):
        obj = _ApiServer(self, bridge)
        self.apiServerList.append(obj)
        self.routerJsonDownstream[obj] = dict()

    def wanPrefixListChanged(self, prefixList):
        self.routerInfo[self.param.uuid]["wan-prefix-list"] = prefixList
        if self.apiClient is not None and self.apiClient.bConnected:
            data = dict()
            data[self.param.uuid] = prefixList
            self.apiClient.send_notification("update-router-wan-prefix-list", data)

    def lanPrefixListChanged(self, prefixList):
        self.routerInfo[self.param.uuid]["lan-prefix-list"] = prefixList
        if self.apiClient is not None and self.apiClient.bConnected:
            data = dict()
            data[self.param.uuid] = prefixList
            self.apiClient.send_notification("update-router-lan-prefix-list", data)

    def clientAdded(self, ipDataDict):
        self.routerInfo[self.param.uuid]["client-list"].update(ipDataDict)
        if self.apiClient is not None and self.apiClient.bConnected:
            data = dict()
            data[self.param.uuid] = ipDataDict
            self.apiClient.send_notification("new-or-update-router-client", data)

    def clientRemoved(self, ipList):
        for ip in ipList:
            if ip in self.routerInfo[self.param.uuid]["client-list"]:
                del self.routerInfo[self.param.uuid]["client-list"][ip]
        if self.apiClient is not None and self.apiClient.bConnected:
            data = dict()
            data[self.param.uuid] = ipList
            self.apiClient.send_notification("delete-router-client", data)

    def dispose(self):
        assert self.apiClient is None
        for s in self.apiServerList:
            s.dispose()


class _ApiClient(JsonApiEndPoint):

    def __init__(self, pObj, ip, port):
        self.pObj = pObj
        self.bConnected = False
        self.bRegistered = False
        sc = Gio.SocketClient.new()
        sc.set_family(Gio.SocketFamily.IPV4)
        sc.set_protocol(Gio.SocketProtocol.TCP)
        sc.connect_to_host_async(ip, port, None, self._on_connect)

    def _on_connect(self, source_object, res):
        try:
            conn = source_object.connect_to_host_async_finish(res)
            super().set_iostream_and_start(conn)
            self.bConnected = True

            # send register command
            data = dict()
            data["my-id"] = self.pObj.param.uuid
            data["router-list"] = dict()
            if True:
                data["router-list"].update(self.pObj.routerInfo)
                for ri in self.pObj.routerInfoDownstream.values():
                    ri = ri.copy()
                    for v in ri.values:
                        if "parent" not in v:
                            v["parent"] = self.pObj.param.uuid
                    data["router-list"].update(ri)
            super().exec_command("register", data, self._on_register_return, self._on_register_error)
        except Exception as e:
            logging.info("Failed to establish cascade API connection, %s" % (e))
            self.pObj.param.wanManager.on_cascade_client_error(e)
            self.close()

    def _on_register_return(self, data):
        self.pObj.upstreamUuid = data["my-id"]
        self.pObj.upstreamRouterInfo = data["router-list"]
        self.pObj.param.wanManager.on_cascade_client_up(data)
        self.bRegistered = True
        logging.info("Cascade API connection established.")

    def _on_register_error(self, excp):
        raise excp

    def on_error(self, excp):
        self.pObj.param.wanManager.on_cascade_client_error(e)
        if not self.bRegistered:
            logging.info("Failed to establish cascade API connection, %s" % (e))
        else:
            logging.info("Cascade API connection disconnected with error, %s" % (e))

    def on_notification_router_add(self, data):
        assert self.bRegistered

        self.pObj.upstreamRouterInfo.update(data)
        self.pObj.param.wanManager.on_cascade_client_router_add(data)

    def on_notification_router_remove(self, data):
        assert self.bRegistered

        for router_id in data:
            del self.pObj.upstreamRouterInfo[router_id]
        self.pObj.param.wanManager.on_cascade_client_router_remove(data)

    def on_notification_router_wan_prefix_list_change(self, data):
        assert self.bRegistered

        for router_id, prefix_list in data:
            self.pObj.upstreamRouterInfo[router_id]["wan-prefix-list"] = prefix_list
        self.pObj.param.wanManager.on_cascade_client_router_wan_prefix_list_change(data)

    def on_notification_router_lan_prefix_list_change(self, data):
        assert self.bRegistered

        for router_id, prefix_list in data:
            self.pObj.upstreamRouterInfo[router_id]["lan-prefix-list"] = prefix_list
        self.pObj.param.wanManager.on_cascade_client_router_lan_prefix_list_change(data)

    def on_notification_router_client_add_or_change(self, data):
        assert self.bRegistered

        for router_id, client_list in data:
            self.pObj.upstreamRouterInfo[router_id]["client-list"] = client_list
        self.pObj.param.wanManager.on_cascade_client_router_client_add_or_change(data)

    def on_notification_router_client_remove(self, data):
        assert self.bRegistered

        for router_id, ip_list in data:
            o = self.pObj.upstreamRouterInfo[router_id]["client-list"]
            for ip in ip_list:
                if ip in o:
                    del o[ip]
        self.pObj.param.wanManager.on_cascade_client_router_client_remove(data)


#        self.bridgeSourceId = "upstream-%s" % (ip)


class _ApiServer(JsonApiServer):

    def __init__(self, pObj, bridge):
        JsonApiServer.__init__(self, _ApiServerClientProcessor, [WrtCommon.bridgeGetIp(bridge)], pObj.param.cascadeApiPort)

        self.pObj = pObj
        self.bridge = bridge

        self.freeIpRange = self.bridge.get_subhost_ip_range()
        self.subhostOwnerDict = dict()

        self.setOneClientPerIp(True)

        self.setClientTerminateCallback(self._clientTerminateCallback)

        self.addCommand("register", _ApiServerClientProcessor._register)
        self.addCommand("new-router", _ApiServerClientProcessor._new_router)
        self.addCommand("delete-router", _ApiServerClientProcessor._delete_router)
        self.addCommand("update-router-wan-prefix-list", _ApiServerClientProcessor._update_router_wan_prefix_list)
        self.addCommand("update-router-lan-prefix-list", _ApiServerClientProcessor._update_router_lan_prefix_list)
        self.addCommand("new-or-update-router-client", _ApiServerClientProcessor._new_or_update_router_client)
        self.addCommand("delete-router-client", _ApiServerClientProcessor._delete_router_client)


class _ApiServerProcessor(JsonApiEndPoint):

    def __init__(self, pObj, conn):
        self.pObj = pObj
        self.downstreamUuid = None
        self.routerInfo = dict()
        super().set_iostream_and_start(conn)

    def on_command_register(self, data, return_callback, errror_callback):
        try:
            self.downstreamUuid = data["my-id"]
            self.routerInfo = data["router-list"]

            data = dict()
            data["my-id"] = self.pObj.param.uuid
            data["router-list"] = dict()
            return_callback(data)
        except Exception as e:
            errror_callback(e)

    def on_notification_new_router(self, data):
        pass

    def on_notification_delete_router(self, data):
        pass

    def on_notification_update_router_wan_prefix_list(self, data):
        pass

    def on_notification_update_router_lan_prefix_list(self, data):
        pass

    def on_notification_new_or_update_router_client(self, data):
        pass

    def on_notification_delete_router_client(self, data):
        pass







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


class _WrtSubhostOwnerData:

    def __init__(self):
        self.ipRange = []
        self.ipDataDict = dict()
