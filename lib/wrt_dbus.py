#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import json
import dbus
import dbus.service
import socket
from wrt_common import WrtCommon


################################################################################
# DBus API Docs
################################################################################
#
# ==== Main Application ====
# Service               org.fpemud.WRT
# Interface             org.fpemud.WRT
# Object path           /
#
# Methods:
#   info:json                                                GetRouterInfo()
#   (suggested_filename:str,content:str,warn_msg:str-list)   GenerateClientScript(lif_plugin_id:str, os_type:str)
#   void                                                     AddWanService(name:str, service:json-str)
#   void                                                     RemoveWanService(name:str)
#   void                                                     AddTrafficFacilityGroup(name:str, priority:int, tfac_group:json-str)
#   void                                                     ChangeTrafficFacilityGroup(name:str, tfac_group:json-str)
#   void                                                     RemoveTrafficFacilityGroup(name:str)

class DbusMainObject(dbus.service.Object):

    def __init__(self, param):
        self.param = param
        self.wanServOwnerDict = dict()          # dict<wan-service-name,owner>
        self.tfacGroupOwnerDict = dict()        # dict<tfac-group-name,owner>

        # register dbus object path
        bus_name = dbus.service.BusName('org.fpemud.WRT', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/org/fpemud/WRT')

    def release(self):
        self.remove_from_connection()

    def onNameOwnerChanged(self, name, old, new):
        # focus on name deletion, filter other circumstance
        if not name.startswith(":") or new != "":
            return
        assert name == old

        # remove wan services
        snamelist = []
        for sname, owner in self.wanServOwnerDict.items():
            if owner == name:
                snamelist.append(sname)
        for sname in snamelist:
            self.param.trafficManager.remove_wan_service(sname)

        # remove traffic facility groups
        snamelist = []
        for sname, owner in self.wanServOwnerDict.items():
            if owner == name:
                snamelist.append(sname)
        for sname in snamelist:
            self.param.trafficManager.remove_tfac_group(sname)

    @dbus.service.method('org.fpemud.WRT', in_signature='', out_signature='s')
    def GetRouterInfo(self):
        ret = dict()

        ret["uuid"] = self.param.uuid
        ret["hostname"] = socket.gethostname()

        if self.param.wanManager.wanConnPlugin is not None:
            plugin = self.param.wanManager.wanConnPlugin
            ret["wconn-plugin"] = dict()
            ret["wconn-plugin"]["name"] = plugin.full_name
            if plugin.is_connected():
                ret["wconn-plugin"]["is-connected"] = True
                ret["wconn-plugin"]["ip"] = plugin.get_ip()
                ret["wconn-plugin"]["is-ip-public"] = self.param.wanManager.wanConnIpIsPublic
            else:
                ret["wconn-plugin"]["is-connected"] = False

        ret["default-bridge"] = dict()
        if True:
            ret["default-bridge"] = dict()
            ret["default-bridge"]["ip"] = WrtCommon.bridgeGetIp(self.param.lanManager.defaultBridge)
            ret["default-bridge"]["mask"] = self.param.lanManager.defaultBridge.get_prefix()[1]

        ret["lif-plugin"] = dict()
        for plugin in self.param.lanManager.lifPluginList:
            ret["lif-plugin"][plugin.full_name] = dict()

        ret["vpns-plugin"] = dict()
        for plugin in self.param.lanManager.vpnsPluginList:
            ret["vpns-plugin"][plugin.full_name] = dict()
            ret["vpns-plugin"][plugin.full_name]["bridge"] = dict()
            ret["vpns-plugin"][plugin.full_name]["bridge"]["name"] = plugin.get_bridge().get_name()
            ret["vpns-plugin"][plugin.full_name]["bridge"]["ip"] = WrtCommon.bridgeGetIp(plugin.get_bridge())
            ret["vpns-plugin"][plugin.full_name]["bridge"]["mask"] = plugin.get_bridge().get_prefix()[1]

        ret["wan-service"] = []
        if True:
            ret["wan-service"] = list(self.param.trafficManager.wanServDict.keys())

        ret["lan-service"] = []
        if True:
            ret["lan-service"] = list(self.param.lanManager.lanServDict.keys())

        ret["tfac-group"] = dict()
        if True:
            for name, group in self.param.trafficManager.tfacGroupDict.items():
                ret["tfac-group"][name] = dict()
                ret["tfac-group"][name]["priority"] = group.priority
                ret["tfac-group"][name]["facilities"] = [tfac["facility_name"] for tfac in group.facility_list]

        for m in self.param.daemon.managerPluginList:
            ret.update(m.get_router_info())

        return json.dumps(ret)

    @dbus.service.method('org.fpemud.WRT', in_signature='ss', out_signature='ssas')
    def GenerateClientScript(self, vpns_plugin_full_name, os_type):
        if os_type not in ["linux", "win32"]:
            raise Exception("Invalid OS type.")

        pluginObj = None
        for po in self.param.lanManager.vpnsPluginList:
            if po.full_name == vpns_plugin_full_name:
                pluginObj = po
                break
        if pluginObj is None:
            raise Exception("The specified plugin does not exist.")

        if self.param.dnsName is not None:
            suggested_filename, content = pluginObj.generate_client_script(self.param.dnsName, os_type)
            if self.param.wanManager.wanConnPlugin is None or not self.param.wanManager.wanConnPlugin.is_connected():
                return (suggested_filename, content, ["Domain name %s is not validated." % (self.param.dnsName)])
            elif socket.gethostbyname(self.param.dnsName) != self.param.wanManager.wanConnPlugin.get_ip():
                return (suggested_filename, content, ["Domain name %s does not resolve to WAN IP address \"%s\"." % (self.param.dnsName, self.param.wanManager.wanConnPlugin.get_ip())])
            else:
                return (suggested_filename, content, [])
        else:
            if self.param.wanManager.wanConnPlugin is None:
                raise Exception("No internet connection.")
            if not self.param.wanManager.wanConnPlugin.is_connected():
                raise Exception("No internet connection.")
            ip = self.param.wanManager.wanConnPlugin.get_ip()
            msgList = ["No domain name specified, using WAN IP address %s as cloud server address." % (ip)]
            if self.param.wanManager.wanConnIpIsPublic is None:
                msgList.append("Internet connection IP address publicity checking is in progress.")
            elif not self.param.wanManager.wanConnIpIsPublic:
                msgList.append("Internet connection IP address is not public.")
            suggested_filename, content = pluginObj.generate_client_script(ip, os_type)
            return (suggested_filename, content, msgList)

    @dbus.service.method('org.fpemud.WRT', sender_keyword='sender', in_signature='ss')
    def AddWanService(self, name, service, sender=None):
        if self.param.trafficManager.has_wan_service(name):
            raise Exception("WAN service \"%s\" already exists." % (name))
        self.param.trafficManager.add_wan_service(name, json.loads(service))
        self.wanServOwnerDict[name] = sender

    @dbus.service.method('org.fpemud.WRT', in_signature='s')
    def RemoveWanService(self, name):
        self.param.trafficManager.remove_wan_service(name)
        del self.wanServOwnerDict[name]

    @dbus.service.method('org.fpemud.WRT', sender_keyword='sender', in_signature='sis')
    def AddTrafficFacilityGroup(self, name, priority, tfac_group, sender=None):
        if self.param.trafficManager.has_tfac_group(name):
            raise Exception("Traffic facility grouop \"%s\" already exists." % (name))
        tfac_group = json.loads(tfac_group)
        checkTrafficFacilityGroup(tfac_group)

        self.param.trafficManager.add_tfac_group(name, priority, tfac_group)
        self.tfacGroupOwnerDict[name] = sender

    @dbus.service.method('org.fpemud.WRT', in_signature='ss')
    def ChangeTrafficFacilityGroup(self, name, tfac_group):
        if name not in self.tfacGroupDict:
            raise Exception("Traffic facility group \"%s\" does not exist." % (name))
        tfac_group = json.loads(tfac_group)
        checkTrafficFacilityGroup(tfac_group)

        self.param.trafficManager.change_tfac_group(name, json.loads(tfac_group))

    @dbus.service.method('org.fpemud.WRT', in_signature='s')
    def RemoveTrafficFacilityGroup(self, name):
        if name not in self.tfacGroupDict:
            raise Exception("Traffic facility group \"%s\" does not exist." % (name))

        self.param.trafficManager.remove_tfac_group(name)
        del self.tfacGroupOwnerDict[name]


################################################################################
# DBus API Docs
################################################################################
#
# ==== Main Application ====
# Service               org.fpemud.IpForward
# Interface             org.fpemud.IpForward
# Object path           /
#
# Methods:
# void                  On()
# void                  Off()
#

class DbusIpForwardObject(dbus.service.Object):

    def __init__(self, param):
        # implement a fake IpForward object, since we always set ip_forward to 1
        bus_name = dbus.service.BusName('org.fpemud.IpForward', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/org/fpemud/IpForward')

    def release(self):
        self.remove_from_connection()

    @dbus.service.method('org.fpemud.IpForward')
    def On(self):
        pass

    @dbus.service.method('org.fpemud.IpForward')
    def Off(self):
        pass


def checkTrafficFacilityGroup(tfac_group):
    i = 0
    for tfac in tfac_group:
        i += 1

        if "facility-name" not in tfac:
            raise Exception("Lacking \"facility-name\" for facility No.%d." % (i))

        if "facility-type" not in tfac:
            raise Exception("Lacking \"facility-type\" for facility \"%s\"." % (tfac["facility-name"]))

        if tfac["facility-type"] == "nameserver":
            if "target" not in tfac:
                raise Exception("Lacking \"target\" for facility \"%s\"." % (tfac["facility-name"]))
            if not isinstance(tfac["target"], list):
                raise Exception("Type of \"target\" is invalid for facility \"%s\"." % (tfac["facility-name"]))
            for item in tfac["target"]:
                msg = "Some element in \"target\" is invalid for facility \"%s\"." % (tfac["facility-name"])
                if not isinstance(item, list):
                    raise Exception(msg)
                if len(item) != 2:
                    raise Exception(msg)
                if not isinstance(item[0], str):
                    raise Exception(msg)
                if not isinstance(item[1], int):
                    raise Exception(msg)

            if "domain-list" not in tfac:
                raise Exception("Lacking \"domain-list\" for facility \"%s\"." % (tfac["facility-name"]))
            if not isinstance(tfac["domain-list"], list):
                raise Exception("Type of \"domain-list\" is invalid for facility \"%s\"." % (tfac["facility-name"]))
            for item in tfac["domain-list"]:
                if not isinstance(item, str):
                    raise Exception("Some element in \"domain-list\" is invalid for facility \"%s\"." % (tfac["facility-name"]))

            continue

        if tfac["facility-type"] == "gateway":
            if "target" not in tfac:
                raise Exception("Lacking \"target\" for facility \"%s\"." % (tfac["facility-name"]))
            msg = "Invalid \"target\" for facility \"%s\"." % (tfac["facility-name"])
            if not isinstance(tfac["target"], list):
                raise Exception(msg)
            if len(tfac["target"]) != 2:
                raise Exception(msg)
            if tfac["target"][0] is not None and not isinstance(tfac["target"][0], str):
                raise Exception(msg)
            if tfac["target"][1] is not None and not isinstance(tfac["target"][1], str):
                raise Exception(msg)

            if "network-list" not in tfac:
                raise Exception("Lacking \"network-list\" for facility \"%s\"." % (tfac["facility-name"]))
            if not isinstance(tfac["network-list"], list):
                raise Exception("Type of \"network-list\" is invalid for facility \"%s\"." % (tfac["facility-name"]))
            for item in tfac["network-list"]:
                msg = "Some element in \"domain-list\" is invalid for facility \"%s\"." % (tfac["facility-name"])
                if not isinstance(item, str):
                    raise Exception(msg)
                try:
                    tnet = ipaddress.IPv4Network(item)
                    if tnet.is_private:
                        raise Exception(msg)
                except ipaddress.AddressValueError:
                    raise Exception(msg)
                except ipaddress.NetmaskValueError:
                    raise Exception(msg)
                except ValueError:
                    raise Exception(msg)

            continue

        raise Exception("Invalid \"facility-type\" for facility \"%s\"." % (tfac["facility-name"]))
