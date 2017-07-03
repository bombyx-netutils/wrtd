#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

from gi.repository import Gio
from wrt_util import JsonApiEndPoint
from wrt_common import WrtCommon


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
#         "2.3.4.5": {
#             "through-vpn": true,
#             "wakeup-mac": "01-02-03-04-05-06",
#         },
#         "3.4.5.6": {
#         },
#     },
# }
#
################################################################################
# Notify: host-add-or-change
################################################################################
#
# {
#     "notify": "host-add-or-change",
#     "data": {
#         "1.2.3.4": {
#             "hostname": "abcd",
#             "wakeup-mac": "01-02-03-04-05-06",
#         },
#     },
# }
#
################################################################################
# Notify: host-remove
################################################################################
#
# {
#     "notify": "host-remove",
#     "data": [
#         "1.2.3.4",
#     ],
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

class WrtSgwManager:

    def __init__(self, param):
        self.param = param

        self.apiServerList = []
        ipList = ["127.0.0.1"] + [WrtCommon.bridgeGetIp(x) for x in WrtCommon.getAllBridges(param)]
        for ip in ipList:
            self.apiServerList.append(_ApiServer(self, ip))

        self.upstreamClientDict = None                  # dict<router-id, dict<ip, data>>
        self.downstreamClientDict = dict()              # dict<downstream-router-id, dict<router-id, dict<ip, data>>>

    def dispose(self):
        # fixme
        pass

    def on_client_add_or_change(self, source_id, ip_data_dict):
        assert len(ip_data_dict) > 0
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("host-add-or-change", ip_data_dict)

    def on_client_remove(self, source_id, ip_list):
        assert len(ip_list) > 0
        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("host-remove", ip_list)

    def on_cascade_upstream_up(self, data):
        self.upstreamClientDict = dict()
        self.on_cascade_upstream_router_add(data["router-list"])

    def on_cascade_upstream_down(self):
        self.on_cascade_upstream_router_remove(self.upstreamClientDict.keys())
        self.upstreamClientDict = None

    def on_cascade_upstream_router_add(self, data):
        for router_id in data.keys():
            self.upstreamClientDict[router_id] = dict()
        self.on_cascade_upstream_router_client_add_or_change(data)

    def on_cascade_upstream_router_remove(self, data):
        notifyData = []

        for router_id in data:
            for ip in self.upstreamClientDict[router_id]:
                notifyData.append(ip)
            del self.upstreamClientDict[router_id]

        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("host-remove", notifyData)

    def on_cascade_upstream_router_client_add_or_change(self, data):
        notifyData = dict()

        for router_id in data.keys():
            if "client-list" not in data[router_id]:
                continue            # used when called by on_cascade_upstream_router_add()
            for ip, data2 in data[router_id]["client-list"].items():
                ip, data2 = _get_ip_data(ip, data2)
                self.upstreamClientDict[router_id][ip] = data2
                notifyData[ip] = data2

        if len(notifyData) > 0:
            for sproc in self.getAllValidApiServerProcessors():
                sproc.send_notification("host-add-or-change", notifyData)

    def on_cascade_upstream_router_client_remove(self, data):
        notifyData = []

        for router_id in data:
            for ip in data[router_id]["client-list"]:
                del self.upstreamClientDict[router_id][ip]
                notifyData.append(ip)

        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("host-remove", notifyData)

    def on_cascade_downstream_up(self, peer_uuid, data):
        self.downstreamClientDict[peer_uuid] = dict()
        self.on_cascade_downstream_new_router(peer_uuid, data["router-list"])

    def on_cascade_downstream_down(self, peer_uuid):
        self.on_cascade_downstream_delete_router(peer_uuid, self.downstreamClientDict[peer_uuid])
        del self.downstreamClientDict[peer_uuid]

    def on_cascade_downstream_new_router(self, peer_uuid, data):
        for router_id in data.keys():
            self.downstreamClientDict[peer_uuid][router_id] = dict()
        self.on_cascade_downstream_new_or_update_router_client(peer_uuid, data)

    def on_cascade_downstream_delete_router(self, peer_uuid, data):
        notifyData = []

        for router_id in data:
            for ip in data[router_id]["client-list"]:
                del self.downstreamClientDict[peer_uuid][router_id][ip]
                notifyData.append(ip)

        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("host-remove", notifyData)

    def on_cascade_downstream_new_or_update_router_client(self, peer_uuid, data):
        notifyData = dict()

        for router_id in data.keys():
            if "client-list" not in data[router_id]:
                continue            # used when called by on_cascade_downstream_new_router()
            for ip, data2 in data[router_id]["client-list"].items():
                ip, data2 = _get_ip_data(ip, data2)
                self.downstreamClientDict[peer_uuid][router_id][ip] = data2
                notifyData[ip] = data2

        if len(notifyData) > 0:
            for sproc in self.getAllValidApiServerProcessors():
                sproc.send_notification("host-add-or-change", notifyData)

    def on_cascade_downstream_delete_router_client(self, peer_uuid, data):
        notifyData = []

        for router_id in data:
            for ip in data[router_id]["client-list"]:
                del self.downstreamClientDict[peer_uuid][router_id][ip]
                notifyData.append(ip)

        for sproc in self.getAllValidApiServerProcessors():
            sproc.send_notification("host-remove", notifyData)

    def getAllValidApiServerProcessors(self):
        ret = []
        for obj in self.apiServerList:
            for sproc in obj.sprocList:
                if sproc.bRegistered:
                    ret.append(sproc)
        return ret


class _ApiServer:

    def __init__(self, pObj, ip):
        self.pObj = pObj

        self.serverListener = Gio.SocketListener.new()
        addr = Gio.InetSocketAddress.new_from_string(ip, self.pObj.param.sgwApiPort)
        self.serverListener.add_address(addr, Gio.SocketType.STREAM, Gio.SocketProtocol.TCP)
        self.serverListener.accept_async(None, self._on_accept)

        self.sprocList = []

    def _on_accept(self, source_object, res):
        conn = source_object.accept_finish(res)
        sproc = _ApiServerProcessor(self.pObj, self, conn)
        self.sprocList.append(sproc)


class _ApiServerProcessor(JsonApiEndPoint):

    def __init__(self, pObj, serverObj, conn):
        self.pObj = pObj
        self.serverObj = serverObj
        super().set_iostream_and_start()

    def on_error(self, e):
        # fixme: add log
        pass

    def on_close(self):
        self.serverObj.sprocList.remove(self)

    def on_command_get_host_list(self, data, return_callback, error_callback):
        data = dict()
        data.update(self.pObj.param.cascadeManager.routerInfo)

        if self.pObj.param.cascadeManager.hasValidApiClient():
            for router in self.pObj.param.cascadeManager.apiClient.routerInfo.values():
                if True:
                    routerIp = self.pObj.param.cascadeManager.apiClient.get_peer_ip()
                    data[routerIp] = dict()
                    data[routerIp]["through-vpn"] = True
                    if "hostname" in router:
                        data[routerIp]["hostname"] = router["hostname"]
                if "client-list" in router:
                    for ip, data2 in router["client-list"]:
                        ip, data2 = _get_ip_data(ip, data2)
                        assert ip not in data
                        data[ip] = data2

        for sproc in self.pObj.param.cascadeManager.getAllValidApiServerProcessors():
            for router in sproc.routerInfo.values():
                if True:
                    data[sproc.get_peer_ip()] = dict()
                    data[sproc.get_peer_ip()]["through-vpn"] = True
                    if "hostname" in router:
                        data[sproc.get_peer_ip()]["hostname"] = router["hostname"]
                if "client-list" in router:
                    for ip, data2 in router["client-list"]:
                        ip, data2 = _get_ip_data(ip, data2)
                        assert ip not in data
                        data[ip] = data2

        return_callback(data)

    def on_command_wakup_host(self, data):
        pass


def _get_ip_data(ip, data):
    data = data.copy()
    if "nat-ip" in data:
        ip = data["nat-ip"]
        del data["nat-ip"]
    data["through-vpn"] = True
    return (ip, data)
