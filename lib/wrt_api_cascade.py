#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-







################################################################################
# Command: register
################################################################################
#
# Request:
# {
#     "command": "register",
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


class WrtCascadeApiServer:

    def __init__(self, param):
        self.param = param
        self.subhostOwnerDict = dict()

        ipList = []
        for bridge in self.param.lanManager.get_bridges():
            ipList.append(bridget.get_ip())

        self.realServer = JsonApiServer(ipList, self.param.cascadeApiPort)
        self.realServer.addCommand("register", self._cmdRegister)
        self.realServer.addCommand("add-subhost", self._addSubhost)
        self.realServer.addCommand("remove-subhost", self._removeSubhost)
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

    def _cmdRegister(self):
        if self.addr not in self.param.lanManager.get_clients():
            throw Exception("invalid source address")

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
                    throw Exception("too many sub-host owners")
            self.pObj.subhostOwnerDict[self.sock] = start

        ipstart = ".".join(self.addr.split(".")[:-1] + [str(start)])
        ipend = ".".join(self.addr.split(".")[:-1] + [str(start + self.param.subHostBlockSize)])
        return {
            "start": ipstart,
            "end": ipend,
        }

    def _addSubhost(self, jsonObj):
        if self.sock not in self.pObj.subhostOwnerDict:
            throw Exception("invalid source address")

    def _removeSubhost(self, jsonObj):
        pass

    def _cmdWakeupHost(self, mac):
        WrtUtil.shell("/usr/bin/wakeonlan -i %s %s" % (self.param.baddr, mac))

        with self.sendLock:
            self.sock.send(json.dumps({
                "return": {},
            }).encode("utf-8"))


class _WrtSubhostOwnerData:

    def __init__(self):
        self.subhostDict = dict()










class WrtCascadeApiClient:

    def __init__(self, param, ip, port):
        self.param = param
        self.realClient = JsonApiClient(ip, port)
        self.realClient.registerNotifyCallback("host-appear", self._notifyHostAppear)
        self.realClient.registerNotifyCallback("host-disappear", self._notifyHostDisappear)
        self.upstreamId = "vpn-%s" % (self.realClient.get_server_ip())

    def dispose(self):
        self.realClient.dispose()

    def registerSubhostOwner(self):
        self.realClient.execCommand("register-subhost-owner")

    def addSubhost(self, ipDataDict):
        self.realClient.execCommand("add-subhost", ipDataDict)

    def removeSubhost(self, ipList):
        self.realClient.execCommand("remove-subhost", ipList)

    def _notifyHostAppear(self, ipDataDict):
        # notify all bridges
        for bridge in self.param.lanManager.get_bridges():
            bridge.on_host_appear(self.upstreamId, ipDataDict)

        # notify downstream
        self.param.apiServer.notifyAppear2(ipDataDict)

    def _notifyHostDisappear(self, ipList):
        # notify all bridges
        for bridge in self.param.lanManager.get_bridges():
            bridge.on_host_disappear(self.upstreamId, ipList)

        # notify downstream
        self.param.apiServer.notifyDisappear2(ipList)

