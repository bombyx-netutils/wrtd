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

        self.apiClientUpCallback = None
        self.apiClientErrorCallback = None
        self.upstreamRouterAddCallback = None
        self.upstreamRouterRemoveCallback = None
        self.upstreamRouterWanPrefixListChangedCallback = None
        self.upstreamRouterLanPrefixListChangedCallback = None
        self.upstreamRouterClientAddOrChangeCallback = None
        self.upstreamRouterClientRemoveCallback = None

        self.apiClientStartThread = None
        self.apiClientIdleQueue = None
        self.apiClientNotifyUpThread = None
        self.apiClientNotifyDownProcessor = None

        # server api
        self.apiServerList = []
        self.routerInfoDownstream = dict()          # dict<api-server, router-json>

    def startApiClient(self, remote_ip, apiClientUpCallback, apiClientErrorCallback, upstreamRouterAddCallback,
                       upstreamRouterRemoveCallback, upstreamRouterWanPrefixListChangedCallback,
                       upstreamRouterLanPrefixListChangedCallback, upstreamRouterClientAddOrChangeCallback,
                       upstreamRouterClientRemoveCallback):
        # exception in any callback function would make WrtCascadeManager bring down the cascade api client.
        # no exception is allowed in apiClientErrorCallback().
        # apiClientErrorCallback() would be called if there's error in cascade-api connection after startApiClient() returns.
        # apiClient is disposed before apiClientErrorCallback() is called.
        # no callback function should be called after the client calls disposeApiClient().

        logging.info("Establishing Cascade API connection.")

        self.apiClientUpCallback = apiClientUpCallback
        self.apiClientErrorCallback = apiClientErrorCallback
        self.upstreamRouterAddCallback = upstreamRouterAddCallback
        self.upstreamRouterRemoveCallback = upstreamRouterRemoveCallback
        self.upstreamRouterWanPrefixListChangedCallback = upstreamRouterWanPrefixListChangedCallback
        self.upstreamRouterLanPrefixListChangedCallback = upstreamRouterLanPrefixListChangedCallback
        self.upstreamRouterClientAddOrChangeCallback = upstreamRouterClientAddOrChangeCallback
        self.upstreamRouterClientRemoveCallback = upstreamRouterClientRemoveCallback

        self.apiClientIdleQueue = WrtUtil.IdleQueue()
        self.apiClientStartThread = _ApiClientStartThread(self, remote_ip)

    def disposeApiClient(self):
        self.apiClientNotifyDownProcessor = None

        if self.apiClientNotifyUpThread is not None:
            self.apiClientNotifyUpThread.stop()
            self.apiClientNotifyUpThread.join()
            self.apiClientNotifyUpThread = None

        self.upstreamRouterInfo = None
        self.upstreamUuid = None

        if self.apiClient is not None:
            self.apiClient.dispose()
            self.apiClient = None

        if self.apiClientStartThread is not None:
            self.apiClientStartThread.join()
            self.apiClientStartThread = None

        if self.apiClientIdleQueue is not None:
            self.apiClientIdleQueue.clear()
            self.apiClientIdleQueue = None

        self.apiClientUpCallback = None
        self.apiClientErrorCallback = None
        self.upstreamRouterAddCallback = None
        self.upstreamRouterRemoveCallback = None
        self.upstreamRouterWanPrefixListChangedCallback = None
        self.upstreamRouterLanPrefixListChangedCallback = None
        self.upstreamRouterClientAddOrChangeCallback = None
        self.upstreamRouterClientRemoveCallback = None

    def startApiServer(self, bridge):
        obj = _ApiServer(self, bridge)
        self.apiServerList.append(obj)
        self.routerJsonDownstream[obj] = dict()

    def wanPrefixListChanged(self, prefixList):
        self.routerInfo[self.param.uuid]["wan-prefix-list"] = prefixList
        if self.apiClient is not None:
            self.apiClientNotifyUpThread.add(self.apiClient.updateRouterWanPrefixList, self.param.uuid, prefixList)

    def lanPrefixListChanged(self, prefixList):
        self.routerInfo[self.param.uuid]["lan-prefix-list"] = prefixList
        if self.apiClient is not None:
            self.apiClientNotifyUpThread.add(self.apiClient.updateRouterLanPrefixList, self.param.uuid, prefixList)

    def clientAdded(self, ipDataDict):
        self.routerInfo[self.param.uuid]["client-list"].update(ipDataDict)
        if self.apiClient is not None:
            self.apiClientNotifyUpThread.add(self.apiClient.newOrUpdateRouterClient, self.param.uuid, ipDataDict)

    def clientRemoved(self, ipList):
        for ip in ipList:
            if ip in self.routerInfo[self.param.uuid]["client-list"]:
                del self.routerInfo[self.param.uuid]["client-list"][ip]
        if self.apiClient is not None:
            self.apiClientNotifyUpThread.add(self.apiClient.deleteRouterClient, self.param.uuid, ipList)

    def dispose(self):
        assert self.apiClient is None
        for s in self.apiServerList:
            s.dispose()


class _ApiClientStartThread(threading.Thread):

    def __init__(self, pObj, remote_ip):
        threading.Thread.__init__(self)
        self.pObj = pObj
        self.remote_ip = remote_ip

    def run(self):
        try:
            apiClient = JsonApiClient(self.remove_ip, self.pObj.param.cascadeApiPort)
            ret = self._register(apiClient, self.pObj.param.uuid, self.pObj.routerInfo, self.pObj.routerInfoDownstream)     # fixme, maybe we shoule copy routerInfo and routerInfoDownstream here instead using it directly
            self.pObj.apiClientIdleQueue.add(self.._idleFuncUpCallback, apiClient, ret)
            break
        except Exception as e:
            apiClient.dispose()
            self.pObj.apiClientIdleQueue.add(self._idleFuncErrorCallback, e)
        finally:
            self.pObj.apiClientStartThread = None

    def _register(self, apiClient, router_id, router_info, router_info_downstream):
        data = dict()
        data["my-id"] = router_id
        data["router-list"] = dict()
        if True:
            data["router-list"].update(router_info)
            for ri in router_info_downstream.values():
                ri = ri.copy()
                for v in ri.values:
                    if "parent" not in v:
                        v["parent"] = router_id
                data["router-list"].update(ri)
        return apiClient.execCommand("register", data)

    def _idleFuncUpCallback(self, apiClient, data):
        try:
            self.pObj.apiClient = apiClient
            self.pObj.upstreamUuid = ret["my-id"]
            self.pObj.upstreamRouterInfo = ret["router-list"]
            self.pObj.apiClientNotifyUpThread = _ApiClientNotifyUpThread(self)
            self.pObj.apiClientNotifyDownProcessor = _ApiClientNotifyDownProcessor(self)
            self.pObj.apiClientUpCallback(data)
            logging.info("Cascade API conection established.")
        except Exception as e:
            logging.error("Failed to establish Cascade API connection, %s", e)
            self.pObj.disposeApiClient()
            self.pObj.apiClientErrorCallback(e)

    def _idleFuncErrorCallback(self, e):
        logging.error("Failed to establish Cascade API connection, %s", e)
        self.pObj.disposeApiClient()
        self.pObj.apiClientErrorCallback(e)


class _ApiClientNotifyUpThread(threading.Thread):

    def __init__(self, pObj):
        threading.Thread.__init__(self)
        self.cmdQueue = queue.Queue()
        self.pObj = pObj
        self.bStop = False

    def stop(self):
        assert not self.bStop
        self.bStop = True

    def newRouter(self, data):
        self.cmdQueue.put(("new-router", data))

    def deleteRouter(self, router_id_list):
        self.cmdQueue.put(("delete-router", router_id_list))

    def updateRouterWanPrefixList(self, router_id, prefix_list):
        data = dict()
        data[router_id] = prefix_list
        self.cmdQueue.put(("update-router-wan-prefix-list", data))

    def updateRouterLanPrefixList(self, router_id, prefix_list):
        data = dict()
        data[router_id] = prefix_list
        self.cmdQueue.put(("update-router-lan-prefix-list", data))

    def newOrUpdateRouterClient(self, router_id, ip_data_dict):
        data = dict()
        data[router_id] = ip_data_dict
        self.cmdQueue.put(("new-or-update-router-client", data))

    def deleteRouterClient(self, router_id, ip_list):
        data = dict()
        data[router_id] = ip_list
        self.cmdQueue.put(("delete-router-client", data))

    def run(self):
        while not self.bStop:
            try:
                cmd, data = self.cmdQueue.get(timeout=1)
                self.cmdQueue.task_done()
                try:
                    ret = self.pObj.apiClient.execCommand(cmd, data)
                    assert ret == dict()
                except Exception as e:
                    self.pObj.apiClientIdleQueue.add(self._idleFunc, e)
                    break
            except queue.Queue.Empty:
                pass

    def _idleFunc(self, e):
        logging.error("Cascade API communication error, %s", e)
        self.pObj.disposeApiClient()
        self.pObj.apiClientErrorCallback(e)


class _ApiClientNotifyDownProcessor:

    def __init__(self, pObj):
        self.pObj = pObj
        self.pObj.apiClient.registerNotifyCallback("router-add",
            lambda data: self.pObj.apiClientIdleQueue.add(self._idleFunc,
                                                          self.on_router_add,
                                                          data))
        self.pObj.apiClient.registerNotifyCallback("router-remove",
            lambda data: self.pObj.apiClientIdleQueue.add(self._idleFunc,
                                                          self.on_router_remove,
                                                          data))
        self.pObj.apiClient.registerNotifyCallback("router-wan-prefix-list-change",
            lambda data: self.pObj.apiClientIdleQueue.add(self._idleFunc,
                                                          self.on_router_wan_prefix_list_change, 
                                                          data))
        self.pObj.apiClient.registerNotifyCallback("router-lan-prefix-list-change",
            lambda data: self.pObj.apiClientIdleQueue.add(self._idleFunc,
                                                          self.on_router_lan_prefix_list_change, 
                                                          data))
        self.pObj.apiClient.registerNotifyCallback("router-client-add-or-change",
            lambda data: self.pObj.apiClientIdleQueue.add(self._idleFunc, 
                                                          self.on_router_client_add_or_change, 
                                                          data))
        self.pObj.apiClient.registerNotifyCallback("router-client-remove",
            lambda data: self.pObj.apiClientIdleQueue.add(self._idleFunc, 
                                                          self.on_router_client_remove, 
                                                          data))

    def on_router_add(self, data):
        self.pObj.upstreamRouterInfo.update(data)
        self.pObj.param.wanManager.on_cascade_upstream_router_add(data)

    def on_router_remove(self, data):
        for router_id in data:
            del self.pObj.upstreamRouterInfo[router_id]
        self.pObj.param.wanManager.on_cascade_upstream_router_remove(data)

    def on_router_wan_prefix_list_change(self, data):
        for router_id, prefix_list in data:
            self.pObj.upstreamRouterInfo[router_id]["wan-prefix-list"] = prefix_list
        self.pObj.param.wanManager.on_cascade_upstream_router_wan_prefix_list_change(data)

    def on_router_lan_prefix_list_change(self, data):
        for router_id, prefix_list in data:
            self.pObj.upstreamRouterInfo[router_id]["lan-prefix-list"] = prefix_list
        self.pObj.param.wanManager.on_cascade_upstream_router_lan_prefix_list_change(data)

    def on_router_client_add_or_change(self, data):
        for router_id, client_list in data:
            self.pObj.upstreamRouterInfo[router_id]["client-list"] = client_list
        self.pObj.param.wanManager.on_cascade_upstream_router_client_add_or_change(data)

    def on_router_client_remove(self, data):
        for router_id, ip_list in data:
            o = self.pObj.upstreamRouterInfo[router_id]["client-list"]
            for ip in ip_list:
                if ip in o:
                    del o[ip]
        self.pObj.param.wanManager.on_cascade_upstream_router_client_remove(data)

    def _idleFunc(self, callback, data):
        try:
            callback(data)
        except Exception as e:
            logging.error("Cascade API communication error, %s", e)
            self.pObj.disposeApiClient()
            self.pObj.apiClientErrorCallback(e)


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

        self.addNotify("router-add")
        self.addNotify("router-remove")
        self.addNotify("router-wan-prefix-list-change")
        self.addNotify("router-lan-prefix-list-change")
        self.addNotify("router-client-add-or-change")
        self.addNotify("router-client-remove")


class _ApiServerClientProcessor(JsonApiServerClientProcessor):

    def __init__(self, server_object, client_address):
        JsonApiServerClientProcessor.__init__(self, server_object, client_address)
        self.downstreamUuid = None
        self.routerInfo = dict()

    def _register(self, data):
        self.downstreamUuid = data["my-id"]
        self.routerInfo = data["router-list"]



    def _new_router(self, data):
        pass

    def _delete_router(self, data):
        pass

    def _update_router_wan_prefix_list(self, data):
        pass

    def _update_router_lan_prefix_list(self, data):
        pass

    def _new_or_update_router_client(self, data):
        pass

    def _delete_router_client(self, data):
        pass



    def _idleFunc(self, callback1, callback2, data):
        try:
            callback1(data)
            callback2(data)
        except Exception as e:
            logging.error("Cascade API communication error, %s", e)
            self.pObj.disposeApiClient()
            self.pObj.apiClientErrorCallback(e)







    def _router_add(self, data):
        self.pObj.upstreamRouterInfo.update(data)

    def _router_remove(self, data):
        for router_id in data:
            del self.pObj.upstreamRouterInfo[router_id]

    def _router_wan_prefix_list_change(self, data):
        for router_id, prefix_list in data:
            self.pObj.upstreamRouterInfo[router_id]["wan-prefix-list"] = prefix_list

    def _router_lan_prefix_list_change(self, data):
        for router_id, prefix_list in data:
            self.pObj.upstreamRouterInfo[router_id]["lan-prefix-list"] = prefix_list

    def _router_client_add_or_change(self, data):
        for router_id, client_list in data:
            self.pObj.upstreamRouterInfo[router_id]["client-list"] = client_list

    def _router_client_remove(self, data):
        for router_id, ip_list in data:
            o = self.pObj.upstreamRouterInfo[router_id]["client-list"]
            for ip in ip_list:
                if ip in o:
                    del o[ip]











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
