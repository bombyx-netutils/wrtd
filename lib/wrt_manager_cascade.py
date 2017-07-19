#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import socket
import signal
import logging
from gi.repository import Gio
from wrt_util import JsonApiEndPoint
from wrt_common import WrtCommon
from wrt_common import Managers


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
#         "router-list": {
#             "c5facfa6-d8c3-4bce-ac13-6abab49c86fc": {
#                 "parent": "c6f7cdad-d2ce-3478-cabc-a3b5445bdfee",
#                 "cascade-vpn": {
#                     "loca1-ip": "1.2.3.4",
#                     "remote-ip": "2.3.4.5",
#                 },
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
# client2server: notification: router-add
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
# client2server: notification: router-remove
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
# client2server: notification: router-wan-prefix-list-change
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
# client2server: notification: router-lan-prefix-list-change
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
# client2server: notification: router-client-add
################################################################################
#
# {
#     "notification": "router-client-add",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "client-list": {
#                 "1.2.3.4": {
#                     "hostname": "abcd",
#                     "wakeup-mac": "01-02-03-04-05-06",
#                 },
#             },
#         ],
#     },
# }
#
################################################################################
# client2server: notification: router-client-change
################################################################################
#
# {
#     "notification": "router-client-change",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "client-list": {
#                 "1.2.3.4": {
#                     "hostname": "abcd",
#                     "wakeup-mac": "01-02-03-04-05-06",
#                 },
#             },
#         ],
#     },
# }
#
################################################################################
# client2server: notification: router-client-remove
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
################################################################################
# server2client: notification: router-add
################################################################################
#
# same as client2server: notification: router-add
#
#
################################################################################
# server2client: notification: router-remove
################################################################################
#
# same as client2server: notification: router-remove
#
#
################################################################################
# server2client: notification: router-cascade-vpn-change
################################################################################
#
# {
#     "notification": "router-cascade-vpn-change",
#     "data": {
#         "c5facfa6-d8c3-4bce-ac13-6abab49c86fc" : {
#             "cascade-vpn": {
#                 "loca1-ip": "1.2.3.4",
#                 "remote-ip": "2.3.4.5",
#             },
#         },
#     },
# }
#
################################################################################
# server2client: notification: router-wan-prefix-list-change
################################################################################
#
# same as client2server: notification: router-wan-prefix-list-change
#
#
################################################################################
# server2client: notification: router-lan-prefix-list-change
################################################################################
#
# same as client2server: notification: router-lan-prefix-list-change
#
#
################################################################################
# server2client: notification: router-client-add
################################################################################
#
# same as client2server: notification: router-client-add
#
#
################################################################################
# server2client: notification: router-client-change
################################################################################
#
# same as client2server: notification: router-client-change
#
#
################################################################################
# server2client: notification: router-client-remove
################################################################################
#
# same as client2server: notification: router-client-remove
#
#


class WrtCascadeManager:

    def __init__(self, param):
        self.param = param

        # router info
        self.routerInfo = dict()
        self.routerInfo[self.param.uuid] = dict()
        self.routerInfo[self.param.uuid]["hostname"] = socket.gethostname()
        if self.param.wanManager.vpnPlugin is not None:
            self.routerInfo[self.param.uuid]["cascade-vpn"] = dict()
        if self.param.wanManager.wanConnPlugin is not None:
            self.routerInfo[self.param.uuid]["wan-prefix-list"] = []
        if True:
            self.routerInfo[self.param.uuid]["lan-prefix-list"] = []
            for bridge in [self.param.lanManager.defaultBridge] + [x.get_bridge() for x in self.param.lanManager.vpnsPluginList]:
                prefix = bridge.get_prefix()
                self.routerInfo[self.param.uuid]["lan-prefix-list"].append(prefix[0] + "/" + prefix[1])
        self.routerInfo[self.param.uuid]["client-list"] = dict()

        # client
        self.apiClient = None

        # servers
        self.apiServerList = []
        self.banUuidList = []

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
        # process by myself
        self.routerInfo[self.param.uuid]["cascade-vpn"] = dict()
        self.routerInfo[self.param.uuid]["cascade-vpn"]["local-ip"] = self.param.wanManager.vpnPlugin.get_local_ip()
        self.routerInfo[self.param.uuid]["cascade-vpn"]["remote-ip"] = self.param.wanManager.vpnPlugin.get_remote_ip()
        assert self.apiClient is None
        self.apiClient = _ApiClient(self, self.param.wanManager.vpnPlugin.get_remote_ip())

        # notify downstream
        data = dict()
        data[self.param.uuid] = dict()
        data[self.param.uuid]["cascade-vpn"] = self.routerInfo[self.param.uuid]["cascade-vpn"]
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-cascade-vpn-change", data)

    def on_wvpn_down(self):
        # process by myself
        if self.apiClient is not None:
            self.apiClient.close()
            self.apiClient = None
        if "cascade-vpn" in self.routerInfo[self.param.uuid]:
            self.routerInfo[self.param.uuid]["cascade-vpn"] = dict()

        # notify downstream
        data = dict()
        data[self.param.uuid] = dict()
        data[self.param.uuid]["cascade-vpn"] = self.routerInfo[self.param.uuid]["cascade-vpn"]
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-cascade-vpn-change", data)

    def on_client_add(self, source_id, ip_data_dict):
        self._clientAddOrChange("add", source_id, ip_data_dict)

    def on_client_change(self, source_id, ip_data_dict):
        self._clientAddOrChange("change", source_id, ip_data_dict)

    def on_client_remove(self, source_id, ip_list):
        assert len(ip_list) > 0

        # process by myself
        for ip in ip_list:
            if ip in self.routerInfo[self.param.uuid]["client-list"]:
                del self.routerInfo[self.param.uuid]["client-list"][ip]
        for sproc in self.getAllValidApiServerProcessors():
            if sproc.get_peer_ip() in ip_list:
                sproc.close()

        # notify upstream
        if self._apiClientCanNotify():
            data = dict()
            data[self.param.uuid] = dict()
            data[self.param.uuid]["client-list"] = ip_list
            self.apiClient.send_notification("router-client-remove", data)

        # notify downstream
        data = dict()
        data[self.param.uuid] = dict()
        data[self.param.uuid]["client-list"] = ip_list
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-remove", data)

    def on_cascade_upstream_up(self, api_client, data):
        self.banUuidList = []
        self.on_cascade_upstream_router_add(api_client, data["router-list"])

    def on_cascade_upstream_down(self, api_client):
        if api_client.routerInfo is not None and len(api_client.routerInfo) > 0:
            self.on_cascade_upstream_router_remove(api_client, api_client.routerInfo.keys())

    def on_cascade_upstream_router_add(self, api_client, data):
        assert len(data) > 0

        # process by myself
        ret = False
        for router_id, item in data.items():
            tlist = _Helper.protocolPrefixListToPrefixList(item.get("wan-prefix-list", []))
            ret |= self.param.prefixPool.setExcludePrefixList("upstream-wan-%s" % (router_id), tlist)
            tlist = _Helper.protocolPrefixListToPrefixList(item.get("lan-prefix-list", []))
            ret |= self.param.prefixPool.setExcludePrefixList("upstream-lan-%s" % (router_id), tlist)
        if ret:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with upstream router %s, autofix it and restart" % (router_id))

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-add", data)

    def on_cascade_upstream_router_remove(self, api_client, data):
        assert len(data) > 0

        # process by myself
        for router_id in data:
            self.param.prefixPool.removeExcludePrefixList("upstream-lan-%s" % (router_id))
            self.param.prefixPool.removeExcludePrefixList("upstream-wan-%s" % (router_id))

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-remove", data)

    def on_cascade_upstream_router_wan_prefix_list_change(self, api_client, data):
        ret = False
        for router_id, item in data.items():
            tlist = _Helper.protocolPrefixListToPrefixList(item["wan-prefix-list"])
            ret |= self.param.prefixPool.setExcludePrefixList("upstream-wan-%s" % (router_id), tlist)
        if ret:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with upstream router %s, autofix it and restart" % (router_id))

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("wan-prefix-list-change", data)

    def on_cascade_upstream_router_lan_prefix_list_change(self, api_client, data):
        # process by myself
        ret = False
        for router_id, item in data.items():
            tlist = _Helper.protocolPrefixListToPrefixList(item["lan-prefix-list"])
            ret |= self.param.prefixPool.setExcludePrefixList("upstream-lan-%s" % (router_id), tlist)
        if ret:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with upstream router %s, autofix it and restart" % (router_id))

        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("lan-prefix-list-change", data)

    def on_cascade_upstream_router_client_add(self, api_client, data):
        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-add", data)

    def on_cascade_upstream_router_client_change(self, api_client, data):
        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-change", data)

    def on_cascade_upstream_router_client_remove(self, api_client, data):
        # notify downstream
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-remove", data)

    def on_cascade_downstream_up(self, sproc, data):
        if len(data["router-list"]) > 0:
            self.on_cascade_downstream_router_add(sproc, data["router-list"])

    def on_cascade_downstream_down(self, sproc):
        self.on_cascade_downstream_router_remove(sproc, list(sproc.get_router_info().keys()))

    def on_cascade_downstream_router_add(self, sproc, data):
        # process by myself
        self._downstreamWanPrefixListCheck(data)

        # notify upstream and other downstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("router-add", data)
        for obj in self.getAllValidApiServerProcessorsExcept(sproc):
            obj.send_notification("router-add", data)

    def on_cascade_downstream_router_remove(self, sproc, data):
        # process by myself
        for router_id in data:
            self.param.prefixPool.removeExcludePrefixList("downstream-wan-%s" % (router_id))

        # notify upstream and other downstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("router-remove", data)
        for obj in self.getAllValidApiServerProcessorsExcept(sproc):
            obj.send_notification("router-remove", data)

    def on_cascade_downstream_router_wan_prefix_list_change(self, sproc, data):
        # process by myself
        self._downstreamWanPrefixListCheck(data)

        # notify upstream and other downstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("router-wan-prefix-list-change", data)
        for obj in self.getAllValidApiServerProcessorsExcept(sproc):
            obj.send_notification("router-wan-prefix-list-change", data)

    def on_cascade_downstream_router_lan_prefix_list_change(self, sproc, data):
        # notify upstream and other downstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("router-lan-prefix-list-change", data)
        for obj in self.getAllValidApiServerProcessorsExcept(sproc):
            obj.send_notification("router-lan-prefix-list-change", data)

    def on_cascade_downstream_router_client_add(self, sproc, data):
        # notify upstream and other downstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("router-client-add", data)
        for obj in self.getAllValidApiServerProcessorsExcept(sproc):
            obj.send_notification("router-client-add", data)

    def on_cascade_downstream_router_client_change(self, sproc, data):
        # notify upstream and other downstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("router-client-change", data)
        for obj in self.getAllValidApiServerProcessorsExcept(sproc):
            obj.send_notification("router-client-change", data)

    def on_cascade_downstream_router_client_remove(self, sproc, data):
        # notify upstream and other downstream
        if self.hasValidApiClient():
            self.apiClient.send_notification("router-client-remove", data)
        for obj in self.getAllValidApiServerProcessorsExcept(sproc):
            obj.send_notification("router-client-remove", data)

    def _clientAddOrChange(self, type, source_id, ip_data_dict):
        assert len(ip_data_dict) > 0

        # process by myself
        self.routerInfo[self.param.uuid]["client-list"].update(ip_data_dict)

        # notify upstream
        if self._apiClientCanNotify():
            data = dict()
            data[self.param.uuid] = dict()
            data[self.param.uuid]["client-list"] = ip_data_dict
            self.apiClient.send_notification("router-client-%s" % (type), data)

        # notify downstream
        data = dict()
        data[self.param.uuid] = dict()
        data[self.param.uuid]["client-list"] = ip_data_dict
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-client-%s" % (type), data)

    def _wanPrefixListChange(self, prefixList):
        prefixList = _Helper.prefixListToProtocolPrefixList(prefixList)

        # process by myself
        self.routerInfo[self.param.uuid]["wan-prefix-list"] = prefixList

        # notify upstream & downstream
        data = dict()
        data[self.param.uuid] = dict()
        data[self.param.uuid]["wan-prefix-list"] = prefixList
        if self._apiClientCanNotify():
            self.apiClient.send_notification("router-wan-prefix-list-change", data)
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("router-wan-prefix-list-change", data)

    def _downstreamWanPrefixListCheck(self, data):
        # check downstream wan-prefix and restart if neccessary
        show_router_id = None
        for router_id, item in data.items():
            if "wan-prefix-list" not in item:
                continue        # used when called by on_cascade_downstream_router_add()
            tlist = _Helper.protocolPrefixListToPrefixList(item["wan-prefix-list"])
            if self.param.prefixPool.setExcludePrefixList("downstream-wan-%s" % (router_id), tlist):
                show_router_id = router_id
        if show_router_id is not None:
            os.kill(os.getpid(), signal.SIGHUP)
            raise Exception("prefix duplicates with downstream router %s, autofix it and restart" % (show_router_id))

    def hasValidApiClient(self):
        return self.apiClient is not None and self.apiClient.bRegistered

    def getAllValidApiServerProcessors(self):
        return self.getAllValidApiServerProcessorsExcept(None)

    def getAllValidApiServerProcessorsExcept(self, sproc):
        ret = []
        for obj in self.apiServerList:
            for sproc2 in obj.sprocList:
                if sproc2.bRegistered and sproc2 != sproc:
                    ret.append(sproc2)
        return ret

    def _apiClientCanNotify(self):
        return self.apiClient is not None and self.apiClient.bConnected


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

    def get_peer_uuid(self):
        return self.peerUuid

    def get_peer_ip(self):
        return self.remoteIp

    def get_router_info(self):
        return self.routerInfo

    def _on_connect(self, source_object, res):
        try:
            conn = source_object.connect_to_host_finish(res)
            super().set_iostream_and_start(conn)

            # send register command
            data = dict()
            data["my-id"] = self.pObj.param.uuid
            data["router-list"] = dict()
            if True:
                data["router-list"].update(self.pObj.routerInfo)
                for sproc in self.pObj.getAllValidApiServerProcessors():
                    data["router-list"].update(sproc.get_router_info())
                    data["router-list"][sproc.peerUuid]["parent"] = self.pObj.param.uuid
            super().exec_command("register", data, self._on_register_return, self._on_register_error)

            self.bConnected = True
        except Exception as e:
            logging.error("Failed to establish CASCADE-API connection", exc_info=True)   # fixme
            Managers.call("on_cascade_upstream_fail", self, e)
            self.close()

    def _on_register_return(self, data):
        self.peerUuid = data["my-id"]
        self.routerInfo = data["router-list"]
        self.bRegistered = True
        logging.info("CASCADE-API connection established.")
        _Helper.logRouterAdd(self.routerInfo)
        Managers.call("on_cascade_upstream_up", self, data)

    def _on_register_error(self, reason):
        m = re.match("UUID (.*) duplicate", reason)
        if m is not None:
            for sproc in self.pObj.getAllValidApiServerProcessors():
                if m.group(1) in sproc.get_router_info():
                    self.pObj.banUuidList.append(m.group(1))
                    sproc.close()
        raise Exception(reason)

    def on_error(self, excp):
        if not self.bRegistered:
            logging.error("Failed to establish CASCADE-API connection.", exc_info=True)      # fixme
            Managers.call("on_cascade_upstream_fail", self, excp)
        else:
            logging.error("CASCADE-API connection disconnected with error.", exc_info=True)  # fixme
            Managers.call("on_cascade_upstream_error", self, excp)

    def on_close(self):
        if not self.bRegistered:
            pass
        else:
            Managers.call("on_cascade_upstream_down", self)
            _Helper.logRouterRemoveAll(self.routerInfo)

    def on_notification_router_add(self, data):
        assert self.bRegistered

        ret = _Helper.upstreamRouterIdDuplicityCheck(self.pObj.param, data)
        if ret is not None:
            uuid, sproc = ret
            if sproc is not None:
                self.pObj.banUuidList.append(uuid)
                sproc.close()
            raise Exception("UUID %s duplicate" % (uuid))

        self.routerInfo.update(data)
        _Helper.logRouterAdd(data)
        Managers.call("on_cascade_upstream_router_add", self, data)

    def on_notification_router_remove(self, data):
        assert self.bRegistered
        Managers.call("on_cascade_upstream_router_remove", self, data)
        _Helper.logRouterRemove(data, self.routerInfo)
        for router_id in data:
            del self.routerInfo[router_id]

    def on_notification_router_cascade_vpn_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["cascade-vpn"] = item["cascade-vpn"]
        Managers.call("on_cascade_upstream_router_cascade_vpn_change", self, data)

    def on_notification_router_wan_prefix_list_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["wan-prefix-list"] = item["wan-prefix-list"]
        Managers.call("on_cascade_upstream_router_wan_prefix_list_change", self, data)

    def on_notification_router_lan_prefix_list_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["lan-prefix-list"] = item["lan-prefix-list"]
        Managers.call("on_cascade_upstream_router_lan_prefix_list_change", self, data)

    def on_notification_router_client_add(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["client-list"].update(item["client-list"])
        _Helper.logRouterClientAdd(data)
        Managers.call("on_cascade_upstream_router_client_add", self, data)

    def on_notification_router_client_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["client-list"].update(item["client-list"])
        # no log needed for client change
        Managers.call("on_cascade_upstream_router_client_change", self, data)

    def on_notification_router_client_remove(self, data):
        assert self.bRegistered
        Managers.call("on_cascade_upstream_router_client_remove", self, data)
        _Helper.logRouterClientRemove(data, self.routerInfo)
        for router_id, item in data.items():
            for ip in item["client-list"]:
                del self.routerInfo[router_id]["client-list"][ip]


class _ApiServer:

    def __init__(self, pObj, bridge):
        self.pObj = pObj

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
        sproc = _ApiServerProcessor(self.pObj, self, conn)
        self.sprocList.append(sproc)
        logging.info("CASCADE-API client %s accepted." % (conn.get_remote_address().get_address().to_string()))
        self.serverListener.accept_async(None, self._on_accept)


class _ApiServerProcessor(JsonApiEndPoint):

    def __init__(self, pObj, serverObj, conn):
        super().__init__()
        self.pObj = pObj
        self.serverObj = serverObj
        self.conn = conn
        self.peerUuid = None
        self.routerInfo = dict()
        self.bRegistered = False
        super().set_iostream_and_start(self.conn)

    def get_peer_uuid(self):
        return self.peerUuid

    def get_peer_ip(self):
        return self.conn.get_remote_address().get_address().to_string()

    def get_router_info(self):
        return self.routerInfo

    def on_error(self, e):
        logging.error("debugXXXXXXXXXXXX", exc_info=True)            # fixme

    def on_close(self):
        if self.bRegistered:
            Managers.call("on_cascade_downstream_down", self)
            _Helper.logRouterRemoveAll(self.routerInfo)
        self.routerInfo = None
        self.peerUuid = None
        logging.info("CASCADE-API client %s disconnected." % (self.get_peer_ip()))
        self.serverObj.sprocList.remove(self)

    def on_command_register(self, data, return_callback, error_callback):
        # receive data
        peerUuid = data["my-id"]
        routerInfo = data["router-list"]

        # check data
        if True:
            uuid = _Helper.downStreamRouterIdDuplicityCheck(self.pObj.param, routerInfo)
            if uuid is not None:
                logging.error("CASCADE-API client %s rejected, UUID %s duplicate." % (self.get_peer_ip(), uuid))
                error_callback("UUID %s duplicate" % (uuid))
                # no need to actively close connection, client would close it
                return

        # save data
        self.peerUuid = peerUuid
        self.routerInfo = routerInfo

        # send reply
        data2 = dict()
        data2["my-id"] = self.pObj.param.uuid
        data2["router-list"] = dict()
        if True:
            data2["router-list"].update(self.pObj.routerInfo)
            if self.pObj.hasValidApiClient():
                data2["router-list"][self.pObj.param.uuid]["parent"] = self.pObj.apiClient.peerUuid
                data2["router-list"].update(self.pObj.apiClient.routerInfo)
            for sproc in self.pObj.getAllValidApiServerProcessors():
                data2["router-list"].update(sproc.routerInfo)
                data2["router-list"][sproc.peerUuid]["parent"] = self.pObj.param.uuid
        return_callback(data2)

        # registered
        self.bRegistered = True
        logging.info("CASCADE-API client %s registered." % (self.get_peer_ip()))
        _Helper.logRouterAdd(self.routerInfo)
        Managers.call("on_cascade_downstream_up", self, data)

    def on_notification_router_add(self, data):
        assert self.bRegistered

        uuid = _Helper.downStreamRouterIdDuplicityCheck(self.pObj.param, data)
        if uuid is not None:
            raise Exception("UUID %s duplicate" % (uuid))

        self.routerInfo.update(data)
        _Helper.logRouterAdd(data)
        Managers.call("on_cascade_downstream_router_add", self, data)

    def on_notification_router_remove(self, data):
        assert self.bRegistered
        Managers.call("on_cascade_downstream_router_remove", self, data)
        _Helper.logRouterRemove(data, self.routerInfo)
        for router_id in data:
            del self.routerInfo[router_id]

    def on_notification_router_wan_prefix_list_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["wan-prefix-list"] = item["wan-prefix-list"]
        Managers.call("on_cascade_downstream_router_wan_prefix_list_change", self, data)

    def on_notification_router_lan_prefix_list_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["lan-prefix-list"] = item["lan-prefix-list"]
        Managers.call("on_cascade_downstream_router_lan_prefix_list_change", self, data)

    def on_notification_router_client_add(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["client-list"].update(item["client-list"])
        _Helper.logRouterClientAdd(data)
        Managers.call("on_cascade_downstream_router_client_add", self, data)

    def on_notification_router_client_change(self, data):
        assert self.bRegistered
        for router_id, item in data.items():
            self.routerInfo[router_id]["client-list"].update(item["client-list"])
        # no log needed for client change
        Managers.call("on_cascade_downstream_router_client_change", self, data)

    def on_notification_router_client_remove(self, data):
        assert self.bRegistered
        Managers.call("on_cascade_downstream_router_client_remove", self, data)
        _Helper.logRouterClientRemove(data, self.routerInfo)
        for router_id, item in data.items():
            for ip in item["client-list"]:
                del self.routerInfo[router_id]["client-list"][ip]


class _Helper:

    def prefixListToProtocolPrefixList(prefixList):
        ret = []
        for prefix in prefixList:
            ret.append(prefix[0] + "/" + prefix[1])
        return ret

    def protocolPrefixListToPrefixList(protocolPrefixList):
        ret = []
        for prefix in protocolPrefixList:
            tlist = prefix.split("/")
            ret.append((tlist[0], tlist[1]))
        return ret

    def upstreamRouterIdDuplicityCheck(param, routerInfo):
        if param.uuid in routerInfo:
            return (param.uuid, None)
        for sproc in param.cascadeManager.getAllValidApiServerProcessors():
            ret = set(sproc.get_router_info()) & set(routerInfo.keys())
            ret = list(ret)
            if len(ret) > 0:
                return (ret[0], sproc)
        return None

    def downStreamRouterIdDuplicityCheck(param, routerInfo):
        if param.uuid in routerInfo:
            return param.uuid
        if param.cascadeManager.hasValidApiClient():
            ret = set(param.cascadeManager.apiClient.get_router_info()) & set(routerInfo.keys())
            ret = list(ret)
            if len(ret) > 0:
                return ret[0]
        for sproc in param.cascadeManager.getAllValidApiServerProcessors():
            ret = set(sproc.get_router_info()) & set(routerInfo.keys())
            ret = list(ret)
            if len(ret) > 0:
                return ret[0]
        return None

    def logRouterAdd(data):
        for router_id, item in data.items():
            if "hostname" in data:
                logging.info("Router %s(UUID:%s) appeared." % (item["hostname"], router_id))
            else:
                logging.info("Router %s appeared." % (router_id))
            if "client-list" in item:
                for ip, data2 in item["client-list"].items():
                    if "hostname" in data2:
                        logging.info("Client %s(IP:%s) appeared." % (data2["hostname"], ip))
                    else:
                        logging.info("Client %s appeared." % (ip))

    def logRouterRemove(data, router_info):
        for router_id in data:
            data2 = router_info[router_id]
            if "client-list" in data2:
                o = data2["client-list"]
                for ip in o.keys():
                    if "hostname" in o[ip]:
                        logging.info("Client %s(IP:%s) disappeared." % (o[ip]["hostname"], ip))
                    else:
                        logging.info("Client %s disappeared." % (ip))
            if "hostname" in data2:
                logging.info("Router %s(UUID:%s) disappeared." % (data2["hostname"], router_id))
            else:
                logging.info("Router %s disappeared." % (router_id))

    def logRouterRemoveAll(router_info):
        _Helper.logRouterRemove(list(router_info.keys()), router_info)

    def logRouterClientAdd(data):
        for router_id, item in data.items():
            for ip, data2 in item["client-list"].items():
                if "hostname" in data2:
                    logging.info("Client %s(IP:%s) appeared." % (data2["hostname"], ip))
                else:
                    logging.info("Client %s appeared." % (ip))

    def logRouterClientRemove(data, router_info):
        for router_id, item in data.items():
            o = router_info[router_id]["client-list"]
            for ip in item["client-list"]:
                if "hostname" in o[ip]:
                    logging.info("Client %s(IP:%s) disappeared." % (o[ip]["hostname"], ip))
                else:
                    logging.info("Client %s disappeared." % (ip))
