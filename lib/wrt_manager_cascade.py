#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import signal
import logging
from gi.repository import Gio
from wrt_util import JsonApiEndPoint
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
#                 "hostname": "abc",
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

        # client
        self.apiClient = None

        # server
        self.apiServerList = []
        self.downstreamDict = dict()

        # start CASCADE-API server for all the bridges
        for plugin in self.param.lanManager.vpnsPluginList:
            self.apiServerList.append(_ApiServer(self, plugin.get_bridge()))
        logging.info("CASCADE-API servers started.")

    def dispose(self):
        for s in self.apiServerList:
            s.close()
        self.apiServerList = []

        if self.apiClient is not None:
            pass                # fixme

    def on_wconn_up(self):
        self._wanPrefixListChange(self.param.wanManager.wanConnPlugin.get_prefix_list())

    def on_wconn_down(self):
        self._wanPrefixListChange([])

    def on_wvpn_up(self):
        assert self.apiClient is None
        self.apiClient = _ApiClient(self, self.param.wanManager.vpnPlugin.get_remote_ip())

    def on_wvpn_down(self):
        if self.apiClient is not None:
            self.apiClient.close()
            self.apiClient = None

    def on_client_add_or_change(self, source_id, ip_data_dict):
        assert len(ip_data_dict) > 0

        # process by myself
        self.routerInfo[self.param.uuid]["client-list"].update(ip_data_dict)

        # notify upstream
        if self.apiClient is not None and self.apiClient.bConnected:
            data = dict()
            data[self.param.uuid] = dict()
            data[self.param.uuid]["client-list"] = ip_data_dict.copy()
            for ip, data2 in data[self.param.uuid]["client-list"]:
                data2["nat-ip"] = self.param.trafficManager.sourceIpDict[source_id][ip][1]
            self.apiClient.send_notification("new-or-update-router-client", data)

        # notify downstream
        data = dict()
        data[self.param.uuid] = dict()
        data[self.param.uuid]["client-list"] = ip_data_dict
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-add-or-change", data)

    def on_client_remove(self, ip_list):
        assert len(ip_list) > 0

        # process by myself
        for ip in ip_list:
            if ip in self.routerInfo[self.param.uuid]["client-list"]:
                del self.routerInfo[self.param.uuid]["client-list"][ip]

        # notify upstream
        if self.apiClient is not None and self.apiClient.bConnected:
            data = dict()
            data[self.param.uuid] = dict()
            data[self.param.uuid]["client-list"] = ip_list
            self.apiClient.send_notification("delete-router-client", data)

        # notify downstream
        data = dict()
        data[self.param.uuid] = dict()
        data[self.param.uuid]["client-list"] = ip_list
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-remove", data)

    def on_cascade_upstream_up(self, data):
        self.on_cascade_upstream_router_add(data["router-list"])

    def on_cascade_upstream_down(self):
        if self.apiClient.routerInfo is not None and len(self.apiClient.routerInfo) > 0:
            self.on_cascade_upstream_router_remove(self.apiClient.routerInfo.keys())

    def on_cascade_upstream_router_add(self, data):
        assert len(data) > 0

        # process by myself
        if self.param.uuid in data.keys():
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("router UUID duplicates, will restart")
        ret = False
        for router_id, item in data.items():
            ret |= self.param.prefixPool.setExcludePrefixList("upstream-wan-%s" % (router_id), item.get("wan-prefix-list", []))
            ret |= self.param.prefixPool.setExcludePrefixList("upstream-lan-%s" % (router_id), item.get("lan-prefix-list", []))
        if ret:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with upstream router %s, autofix it and restart" % (router_id))

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-add", data)

    def on_cascade_upstream_router_remove(self, data):
        assert len(data) > 0

        # process by myself
        for router_id in data:
            self.param.prefixPool.removeExcludePrefixList("upstream-lan-%s" % (router_id))
            self.param.prefixPool.removeExcludePrefixList("upstream-wan-%s" % (router_id))

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-remove", data)

    def on_cascade_upstream_router_wan_prefix_list_change(self, data):
        ret = False
        for router_id, item in data.items():
            ret |= self.param.prefixPool.setExcludePrefixList("upstream-wan-%s" % (router_id), item["wan-prefix-list"])
        if ret:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with upstream router %s, autofix it and restart" % (router_id))

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("wan-prefix-list-change", data)

    def on_cascade_upstream_router_lan_prefix_list_change(self, data):
        # process by myself
        ret = False
        for router_id, item in data.items():
            ret |= self.param.prefixPool.setExcludePrefixList("upstream-lan-%s" % (router_id), item["lan-prefix-list"])
        if ret:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with upstream router %s, autofix it and restart" % (router_id))

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("lan-prefix-list-change", data)

    def on_cascade_upstream_router_client_add_or_change(self, data):
        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-add-or-change", data)

    def on_cascade_upstream_router_client_remove(self, data):
        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-remove", data)

    def on_cascade_downstream_up(self, peer_uuid, data):
        self.downstreamDict[peer_uuid] = []
        if len(data["router-list"]) > 0:
            self.on_cascade_downstream_new_router(peer_uuid, data["router-list"])

    def on_cascade_downstream_down(self, peer_uuid):
        self.on_cascade_downstream_delete_router(peer_uuid, self.downstreamDict[peer_uuid])
        del self.downstreamDict[peer_uuid]

    def on_cascade_downstream_new_router(self, peer_uuid, data):
        self.downstreamDict[peer_uuid] += data

        # notify upstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("new-router", data)

    def on_cascade_downstream_delete_router(self, peer_uuid, data):
        for router_id in data:
            self.downstreamDict[peer_uuid].remove(router_id)

        # notify upstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("delete-router", data)

    def on_cascade_downstream_update_router_wan_prefix_list(self, peer_uuid, data):
        # notify upstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("update-router-wan-prefix-list", data)

    def on_cascade_downstream_update_router_lan_prefix_list(self, peer_uuid, data):
        # notify upstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("update-router-lan-prefix-list", data)

    def on_cascade_downstream_new_or_update_router_client(self, peer_uuid, data):
        # notify upstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("new-or-update-router-client", data)

    def on_cascade_downstream_delete_router_client(self, peer_uuid, data):
        # notify upstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("delete-router-client", data)

    def _wanPrefixListChange(self, prefixList):
        self.routerInfo[self.param.uuid]["wan-prefix-list"] = prefixList

        # notify upstream
        if self.apiClient is not None and self.apiClient.bConnected:
            data = dict()
            data[self.param.uuid] = prefixList
            self.apiClient.send_notification("update-router-wan-prefix-list", data)

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            data = dict()
            data[self.param.uuid] = prefixList
            sproc.send_notification("router-wan-prefix-list-change", data)

    def hasValidApiClient(self):
        return self.apiClient is not None and self.apiClient.bRegistered

    def getAllValidApiServerProcessors(self):
        ret = []
        for obj in self.apiServerList:
            for sproc in obj.sprocList:
                if sproc.bRegistered:
                    ret.append(sproc)
        return ret


class _ApiClient(JsonApiEndPoint):

    # no exception is allowed in on_cascade_upstream_fail(),  on_cascade_upstream_error(),  on_cascade_upstream_down().
    # on_cascade_upstream_fail() would be called if there's error before client is registered.
    # on_cascade_upstream_error() would be called if there's error after client is registered.

    def __init__(self, pObj, remote_ip):
        super().__init__()
        self.pObj = pObj
        self.remoteIp = remote_ip

        sc = Gio.SocketClient.new()
        sc.set_family(Gio.SocketFamily.IPV4)
        sc.set_protocol(Gio.SocketProtocol.TCP)

        logging.info("Establishing CASCADE-API connection.")
        self.peerUuid = None
        self.routerInfo = None
        self.bConnected = False
        self.bRegistered = False
        sc.connect_to_host_async(self.remoteIp, self.pObj.param.cascadeApiPort, None, self._on_connect)

    def get_peer_ip(self):
        return self.remoteIp

    def _on_connect(self, source_object, res):
        try:
            conn = source_object.connect_to_host_finish(res)
            super().set_iostream_and_start(conn)
            self.bConnected = True

            # send register command
            data = dict()
            data["my-id"] = self.pObj.param.uuid
            data["router-list"] = dict()
            if True:
                data["router-list"].update(self.pObj.routerInfo)
                for sproc in self.pObj.getAllValidApiServerProcessors():
                    data["router-list"].update(sproc.routerInfo)
                    data["router-list"][sproc.peerUuid]["parent"] = self.pObj.param.uuid
            super().exec_command("register", data, self._on_register_return, self._on_register_error)
        except Exception as e:
            logging.info("Failed to establish CASCADE-API connection, %s" % (e))
            WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_fail", e)
            self.close()

    def _on_register_return(self, data):
        self.peerUuid = data["my-id"]
        self.routerInfo = data["router-list"]
        self.bRegistered = True
        logging.info("CASCADE-API connection established.")
        WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_up", data)

    def _on_register_error(self, reason):
        raise Exception(reason)

    def on_error(self, excp):
        if not self.bRegistered:
            logging.info("Failed to establish CASCADE-API connection, %s" % (excp))
            WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_fail", excp)
        else:
            logging.info("CASCADE-API connection disconnected with error, %s" % (excp))
            WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_error", excp)

    def on_close(self):
        if not self.bRegistered:
            pass
        else:
            WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_down")

    def on_notification_router_add(self, data):
        assert self.bRegistered
        self.routerInfo.update(data)
        WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_router_add", data)

    def on_notification_router_remove(self, data):
        assert self.bRegistered
        for router_id in data:
            del self.routerInfo[router_id]
        WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_router_remove", data)

    def on_notification_router_wan_prefix_list_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["wan-prefix-list"] = item["wan-prefix-list"]
        WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_router_wan_prefix_list_change", data)

    def on_notification_router_lan_prefix_list_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["lan-prefix-list"] = item["lan-prefix-list"]
        WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_router_lan_prefix_list_change", data)

    def on_notification_router_client_add_or_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["client-list"].update(item["client-list"])
        WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_router_client_add_or_change", data)

    def on_notification_router_client_remove(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            o = self.routerInfo[router_id]["client-list"]
            for ip in item["client-list"]:
                if ip in o:
                    del o[ip]
        WrtCommon.callManagers(self.pObj.param, "on_cascade_upstream_router_client_remove", data)


class _ApiServer:

    def __init__(self, pObj, bridge):
        self.pObj = pObj
        self.freeSubhostIpRangeList = bridge.get_subhost_ip_range()

        self.serverListener = Gio.SocketListener.new()
        addr = Gio.InetSocketAddress.new_from_string(WrtCommon.bridgeGetIp(bridge), self.pObj.param.cascadeApiPort)
        self.serverListener.add_address(addr, Gio.SocketType.STREAM, Gio.SocketProtocol.TCP)
        self.serverListener.accept_async(None, self._on_accept)

        self.sprocList = []

    def close(self):
        for sproc in self.sprocList:
            sproc.close()
        self.serverListener.close()

    def _on_accept(self, source_object, res):
        conn, dummy = source_object.accept_finish(res)
        if self.freeSubhostIpRangeList == []:
            conn.close()
            logging.info("CASCADE-API client %s rejected, no subhost ip range available." % (conn.get_remote_address().get_address().to_string()))
            return

        sproc = _ApiServerProcessor(self.pObj, self, conn, self.freeSubhostIpRangeList.pop(0))
        self.sprocList.append(sproc)
        logging.info("CASCADE-API client %s accepted." % (conn.get_remote_address().get_address().to_string()))
        self.serverListener.accept_async(None, self._on_accept)


class _ApiServerProcessor(JsonApiEndPoint):

    def __init__(self, pObj, serverObj, conn, subhostIpRange):
        super().__init__()
        self.pObj = pObj
        self.serverObj = serverObj
        self.conn = conn
        self.subhostIpRange = subhostIpRange
        self.bRegistered = False
        self.peerUuid = None
        self.routerInfo = dict()
        super().set_iostream_and_start(self.conn)

    def get_peer_ip(self):
        return self.conn.get_remote_address().get_address().to_string()

    def close(self):
        pass            # fixme

    def on_error(self, e):
        logging.info("debugXXXXXXXXXXXX", e)            # fixme
        self.serverObj.sprocList.remove(self)
        self.serverObj.freeSubhostIpRangeList.append(self.subhostIpRange)

    def on_close(self):
        if self.bRegistered:
            WrtCommon.callManagers(self.pObj.param, "on_cascade_downstream_down", self.peerUuid)
        logging.info("CASCADE-API client %s(UUID:%s) disconnected." % (self.get_peer_ip(), self.peerUuid))

    def on_command_register(self, data, return_callback, errror_callback):
        # receive data
        self.peerUuid = data["my-id"]
        self.routerInfo = data["router-list"]
        WrtCommon.callManagers(self.pObj.param, "on_cascade_downstream_up", self.peerUuid, data)

        # send data
        data = dict()
        data["my-id"] = self.pObj.param.uuid
        data["subhost-start"] = self.subhostIpRange[0]
        data["subhost-end"] = self.subhostIpRange[1]
        data["router-list"] = dict()
        if True:
            data["router-list"].update(self.pObj.routerInfo)
            if self.pObj.hasValidApiClient():
                data["router-list"][self.pObj.param.uuid]["parent"] = self.pObj.apiClient.peerUuid
                data["router-list"].update(self.pObj.apiClient.routerInfo)
            for sproc in self.pObj.getAllValidApiServerProcessors():
                if sproc != self:
                    data["router-list"].update(sproc.routerInfo)
                    data["router-list"][sproc.peerUuid]["parent"] = self.pObj.param.uuid
        return_callback(data)

        # registered
        self.bRegistered = True
        logging.info("CASCADE-API client %s(UUID:%s) registered." % (self.get_peer_ip(), self.peerUuid))

    def on_notification_new_router(self, data):
        assert self.bRegistered
        self.routerInfo.update(data)
        WrtCommon.callManagers(self.pObj.param, "on_cascade_downstream_new_router", self.peerUuid, data)

    def on_notification_delete_router(self, data):
        assert self.bRegistered
        for router_id in data:
            del self.routerInfo[router_id]
        WrtCommon.callManagers(self.pObj.param, "on_cascade_downstream_delete_router", self.peerUuid, data)

    def on_notification_update_router_wan_prefix_list(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["wan-prefix-list"] = item["wan-prefix-list"]
            WrtCommon.callManagers(self.pObj.param, "on_cascade_downstream_update_router_wan_prefix_list", self.peerUuid, data)

    def on_notification_update_router_lan_prefix_list(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["lan-prefix-list"] = item["lan-prefix-list"]
        WrtCommon.callManagers(self.pObj.param, "on_cascade_downstream_update_router_lan_prefix_list", self.peerUuid, data)

    def on_notification_new_or_update_router_client(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["client-list"].update(item["client-list"])
        WrtCommon.callManagers(self.pObj.param, "on_cascade_downstream_new_or_update_router_client", self.peerUuid, data)

    def on_notification_delete_router_client(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            o = self.routerInfo[router_id]["client-list"]
            for ip in item["client-list"]:
                if ip in o:
                    del o[ip]
        WrtCommon.callManagers(self.pObj.param, "on_cascade_downstream_delete_router_client", self.peerUuid, data)
