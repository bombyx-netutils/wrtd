#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
from wrt_util import WrtUtil
from wrt_util import JsonApiServer
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

class WrtSgwApiServer:

    def __init__(self, param):
        self.param = param
        self.subhostOwnerDict = dict()

        ipList = ["127.0.0.1"]
        ipList += [WrtCommon.bridgeGetIp(x) for x in self.param.lanManager.get_bridges()]
        self.realServer = JsonApiServer(ipList, self.param.sgwApiPort)

        self.realServer.addCommand("get-host-list", self._cmdGetHostList)
        self.realServer.addCommand("wakeup-host", self._cmdWakeupHost)
        self.realServer.addNotify("host-appear")
        self.realServer.addNotify("host-disappear")

    def dispose(self):
        self.realServer.dispose()

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

    def _cmdGetHostList(self, addr):
        dataDict = dict()
        for fn in glob.glob(os.path.join(self.param.tmpDir, "hosts.d", "*")):
            for ip, hostname in WrtUtil.readDnsmasqHostFile(fn):
                dataDict[ip] = {"hostname": hostname}
        for r in WrtUtil.readDnsmasqLeaseFile(os.path.join(self.param.tmpDir, "dnsmasq.leases")):
            ip = r[1]
            dataDict[ip] = {"mac": r[0]}
            if r[2] != "":
                dataDict[ip]["hostname"] = r[2]

        return dataDict

    def _cmdWakeupHost(self, addr, mac):
        assert False
        # WrtUtil.shell("/usr/bin/wakeonlan -i %s %s" % (self.param.baddr, mac))
        # return {}
