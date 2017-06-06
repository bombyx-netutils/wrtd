#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
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

        print("Internet Connection:")
        print("")

        print("Cascade VPN:")
        print("")

        print("LAN Interface:")
        print("")

        print("Clients:")
        print("")

        print("Upstream Hosts:")
        print("?")

    def cmdGenerateClientScript(self, vpns_plugin_full_name, ostype):
        dbusObj = dbus.SystemBus().get_object('org.fpemud.WRT', '/org/fpemud/WRT')
        if dbusObj is None:
            raise Exception("not started")

        fn, buf = dbusObj.GenerateClientScript(vpns_plugin_full_name, ostype, dbus_interface="org.fpemud.WRT")
        with open(fn, "w") as f:
            f.write(buf)
        os.chmod(fn, 0o755)

        print("Client script generated as ./%s" % (fn))

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
