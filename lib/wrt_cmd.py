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

        print("Internet Connection:")
        print(self._addIndent(dbusObj.GetWanConnInfo(dbus_interface="org.fpemud.WRT")))
        print("")

        print("LAN Interface:")
        print(self._addIndent(dbusObj.GetLanInterfaceInfo(dbus_interface="org.fpemud.WRT")))

        print("Clients:")
        msg = "\n".join(dbusObj.GetClients(dbus_interface="org.fpemud.WRT"))
        print(self._addIndent(msg))
        print("")

        # iplist = []
        # for fn in glob.glob(os.path.join(self.param.tmpDir, "vpn-*-self.hosts")):
        #     for ip, hostname in WrtUtil.readDnsmasqHostFile(fn):
        #         self._showOneClient(ip, hostname)
        #         iplist.append(ip)
        # for fn in glob.glob(os.path.join(self.param.tmpDir, "*.leases")):
        #     for mac, ip, hostname in WrtUtil.readDnsmasqLeaseFile(fn):
        #         if ip in iplist:
        #             continue
        #         assert hostname is ""
        #         self._showOneClient(ip, hostname)

        print("Upstream Hosts:")
        print("?")

    def cmdGenerateClientScript(self, lif_plugin_id, ostype):
        dbusObj = dbus.SystemBus().get_object('org.fpemud.WRT', '/org/fpemud/WRT')
        if dbusObj is None:
            raise Exception("not started")
        fn, buf = dbusObj.GenerateClientScript(lif_plugin_id, ostype, dbus_interface="org.fpemud.WRT")
        with open(fn, "w") as f:
            f.write(buf)
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
