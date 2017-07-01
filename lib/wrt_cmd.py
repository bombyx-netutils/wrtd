#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import json
import dbus
from wrt_util import WrtUtil


class WrtSubCmdMain:

    def __init__(self, param):
        self.param = param

    def cmdShow(self):
        dbusObj = dbus.SystemBus().get_object('org.fpemud.WRT', '/org/fpemud/WRT')
        if dbusObj is None:
            raise Exception("not started")
        info = json.loads(dbusObj.GetRouterInfo(dbus_interface="org.fpemud.WRT"))

        print("Router Information:")
        if True:
            print("    Hostname: " + info["cascade"]["router-list"][info["cascade"]["my-id"]].get("hostname", "None"))
            print("    UUID:     " + info["cascade"]["my-id"])
        print("")

        print("Internet Connection:")
        if "wconn-plugin" not in info:
            print("    None.")
        else:
            print("    Plugin: " + info["wconn-plugin"]["name"])
            if info["wconn-plugin"]["is-connected"]:
                print("    Status: Connected")
                print("    IP:     " + info["wconn-plugin"]["ip"] + " " + ("(public)" if info["wconn-plugin"]["is-ip-public"] else "(behind NAT)"))
            else:
                print("    Status: Not connected")
        print("")

        while True:
            myData = info["cascade"]["router-list"][info["cascade"]["my-id"]]
            if "parent" not in myData:
                break
            print("Cascade Upstream:")
            print("    Plugin: " + info["wvpn-plugin"]["name"])
            if True:
                upstreamId = myData["parent"]
                upstreamData = info["cascade"]["router-list"][upstreamId]
                if "hostname" in upstreamData:
                    upstreamName = "%s(%s)" % (upstreamData["hostname"], upstreamId)
                else:
                    upstreamName = upstreamId
                print("    Name:   " + upstreamName)
            print("")
            break

        while True:
            downstreamIdList = []
            for routerId, routerData in info["cascade"]["router-list"].items():
                if routerData.get("parent", None) == info["cascade"]["my-id"]:
                    downstreamIdList.append(routerId)
            if len(downstreamIdList) == 0:
                break
            print("Cascade Downstream:")
            for downstreamId in downstreamIdList:
                downstreamData = info["cascade"]["router-list"][downstreamId]
                if "hostname" in downstreamData:
                    downstreamName = "%s(%s)" % (downstreamData["hostname"], downstreamId)
                else:
                    downstreamName = downstreamId
                print("    " + downstreamName)
            print("")
            break

        print("Clients:")
        for routerId, routerData in info["cascade"]["router-list"].items():
            if "client-list" in routerData:
                if "hostname" in routerData:
                    routerName = "%s(%s)" % (routerData["hostname"], routerId)
                else:
                    routerName = routerId
                print("    " + routerName + ":")
                for clientIp, clientData in routerData["client-list"]:
                    if "nat-ip" in clientData:
                        clientIp = clientData["nat-ip"]
                    if "hostname" in clientData:
                        clientName = "%s(%s)" % (clientData["hostname"], clientIp)
                    else:
                        clientName = clientIp
                    print("        " + clientName)
        print("")

    def cmdGenerateClientScript(self, vpns_plugin_full_name, ostype):
        dbusObj = dbus.SystemBus().get_object('org.fpemud.WRT', '/org/fpemud/WRT')
        if dbusObj is None:
            raise Exception("not started")

        fn, buf, warnList = dbusObj.GenerateClientScript(vpns_plugin_full_name, ostype, dbus_interface="org.fpemud.WRT")
        with open(fn, "w") as f:
            f.write(buf)
        os.chmod(fn, 0o755)

        print("Client script generated as \"./%s\"." % (fn))
        for warn in warnList:
            print("WARN: %s" % (warn))

    def _showOneClient(self, ip, hostname):
        if hostname != "":
            hostnameStr = "%s (%s)" % (hostname, ip)
        else:
            hostnameStr = "(%s)" % (ip)
        fname = os.path.join(self.param.tmpDir, "subhosts.d", "owner.%s" % (ip))
        if not os.path.exists(fname):
            print("    " + hostnameStr)
        else:
            print(hostnameStr + ":")
            for sip, shostname in WrtUtil.readDnsmasqHostFile(fname):
                print("        " + shostname + " (" + sip + ")")

    def _addIndent(self, msg):
        assert not msg.endswith("\n")
        linelist = msg.split("\n")
        linelist = ["    " + x for x in linelist]
        return "\n".join(linelist)


class _AsciiTree:

    def __init__(self, name):
        assert len(name) > 0
        self.name = name
        self.children = []

    def add_child(self, name):
        assert len(name) > 0
        return self.children.append(_AsciiTree(name))

    def get_ascii(self):
        nameLenList = []
        i = 0
        while True:
            ret = self._get_namelen(i)
            if ret == 0:
                break
            nameLenList.append(ret)
            i += 1
        return ""           # fixme

    def _get_namelen(self, level):
        if level == 0:
            return len(self.name)
        else:
            ret = 0
            for child in self.children:
                ret = max(ret, child._get_namelen(level - 1))
            return ret
