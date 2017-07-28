#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import uuid
import glob
import json
import random
import ipaddress
from collections import OrderedDict
from wrt_util import WrtUtil


class WrtCommon:

    @staticmethod
    def loadUuid(param):
        if os.path.exists(param.dataFile):
            cfgObj = None
            with open(param.dataFile, "r") as f:
                cfgObj = json.load(f)
            param.uuid = cfgObj["uuid"]
            return False
        else:
            param.uuid = WrtCommon.generateAndSaveUuid(param)
            return True

    @staticmethod
    def generateAndSaveUuid(param):
        cfgObj = dict()
        cfgObj["uuid"] = str(uuid.uuid4())
        with open(param.dataFile, "w") as f:
            json.dump(cfgObj, f)
        return cfgObj["uuid"]

    @staticmethod
    def bridgeGetIp(bridge):
        return str(ipaddress.IPv4Address(bridge.get_prefix()[0]) + 1)

    @staticmethod
    def getAllBridges(param):
        ret = [param.lanManager.defaultBridge]
        for plugin in param.lanManager.vpnsPluginList:
            ret.append(plugin.get_bridge())
        return ret


class PluginHub:

    def __init__(self, param):
        self.param = param

    def getPluginList(self, prefix):
        ret = []
        for fn in glob.glob(os.path.join(self.param.libDir, "plugins", prefix + "_*")):
            modname = fn
            modname = modname[len(self.param.libDir + "/"):]
            modname = modname.replace("/", ".")
            exec("import %s" % (modname))
            ret += eval("%s.get_plugin_list()" % (modname))
        return ret

    def getPlugin(self, prefix, name, instance_name=""):
        for fn in glob.glob(os.path.join(self.param.libDir, "plugins", prefix + "_*")):
            modname = fn
            modname = modname[len(self.param.libDir + "/"):]
            modname = modname.replace("/", ".")
            exec("import %s" % (modname))
            if name in eval("%s.get_plugin_list()" % (modname)):
                obj = eval("%s.get_plugin(\"%s\")" % (modname, name))
                if instance_name != "":
                    obj.full_name = name + "-" + instance_name
                else:
                    obj.full_name = name
                return obj
        raise Exception("%s plugin %s does not exist" % (prefix, name))


class ManagerCaller:

    def __init__(self, param):
        self.param = param

        self.callRecord = dict()
        self.callRecord["traffic"] = dict()
        self.callRecord["wan"] = dict()
        self.callRecord["lan"] = dict()

        self.managerDict = OrderedDict()

    def add_manager(self, name, manager):
        self.callRecord[name] = dict()
        self.managerDict[name] = manager

    def call(self, funcName, *args):
        self._callFunc("traffic", self.param.trafficManager, funcName, *args)
        self._callFunc("wan", self.param.wanManager, funcName, *args)
        self._callFunc("lan", self.param.lanManager, funcName, *args)
        for name, manager in self.managerDict.items():
            self._callFunc(name, manager, funcName, *args)

    def _callFunc(self, objName, obj, funcName, *args):
        if obj is None:
            return

        if funcName.endswith("_down"):
            upFuncName = re.sub("_down$", "_up", funcName)
            if upFuncName not in self.callRecord[objName]:
                return
            if hasattr(obj, funcName):
                getattr(obj, funcName)(*args)
            del self.callRecord[objName][upFuncName]
        else:
            if hasattr(obj, funcName):
                getattr(obj, funcName)(*args)
            if funcName.endswith("_up"):
                self.callRecord[objName][funcName] = True


class PrefixPool:

    def __init__(self, dataFile):
        self.dataFile = dataFile
        self.defaultExcludePrefixList = [
            ("192.168.0.0", "255.255.255.0"),
            ("192.168.1.0", "255.255.255.0"),
            ("192.168.2.0", "255.255.255.0"),
        ]
        self.excludePrefixDict = dict()     # dict<key, list<prefix-ip, prefix-mask>>
        self.prefixList = []                # list<prefix-ip, prefix-mask, used-flag>
        self._load()

    def setExcludePrefixList(self, key, prefixList):
        """Returns True means conflict is found and solved, reboot needed"""

        ret = False

        # get conflict items
        idxList = []
        for i in range(0, len(self.prefixList)):
            if WrtUtil.prefixConflictWithPrefixList(self.prefixList[i], prefixList):
                idxList.append(i)
                if self.prefixList[i][2]:
                    ret = True              # program restart needed
                break

        # get a reference list for create new prefix
        refList = []
        for i in range(0, len(self.prefixList)):
            if i not in idxList:
                refList.append(self.prefixList[i])

        # create new prefix for conflict items
        for i in idxList:
            pip, pmask = self._createNewPrefix(refList + prefixList)
            self.prefixList[i] = (pip, pmask, False)

        self.excludePrefixDict[key] = prefixList
        self._save()
        return ret

    def removeExcludePrefixList(self, key):
        if key in self.excludePrefixDict:
            del self.excludePrefixDict[key]

    def usePrefix(self):
        # use a prefix in pool
        for i in range(0, len(self.prefixList)):
            ip, mask, used = self.prefixList[i]
            if not used:
                self.prefixList[i] = (ip, mask, True)
                return (ip, mask)

        # get exluded prefix list
        tl = self.prefixList
        for l in self.excludePrefixDict.values():
            tl += l

        # create a new prefix
        pip, pmask = self._createNewPrefix(tl)
        self.prefixList.append((pip, pmask, True))
        self._save()
        return (pip, pmask)

    def getPrefixList(self):
        ret = []
        for ip, mask, used in self.prefixList:
            ret.append((ip, mask))
        return ret

    def shrink(self):
        list2 = []
        for ip, mask, used in self.prefixList:
            if used:
                list2.append((ip, mask))
        self.prefixList = list2
        self._save()

    def _load(self):
        if not os.path.exists(self.dataFile):
            self.prefixList = []
        else:
            cfgObj = None
            with open(self.dataFile, "r") as f:
                cfgObj = json.load(f)
            for t in cfgObj:
                prefix = t.split("/")[0]
                mask = t.split("/")[1]
                self.prefixList.append((prefix, mask, False))

    def _save(self):
        cfgObj = []
        for ip, mask, used in self.prefixList:
            cfgObj.append(ip + "/" + mask)
        with open(self.dataFile, "w") as f:
            f.write(json.dumps(cfgObj))

    def _createNewPrefix(self, excludeList):
        item = None
        while True:
            item = ("192.168.%d.0" % (random.randint(0, 255)), "255.255.255.0")
            if WrtUtil.prefixConflictWithPrefixList(item, self.defaultExcludePrefixList):
                continue
            if WrtUtil.prefixConflictWithPrefixList(item, excludeList):
                continue
            break
        assert item is not None
        return item


class TemplateBridge:

    def get_name(self):
        assert False

    def get_prefix(self):
        # returns (ip, mask)
        assert False

    def get_bridge_id(self):
        assert False

    def on_source_add(self, source_id):
        assert False

    def on_source_remove(self, source_id):
        assert False

    def on_host_add(self, source_id, ip_data_dict):
        assert False

    def on_host_change(self, source_id, ip_data_dict):
        assert False

    def on_host_remove(self, source_id, ip_list):
        assert False

    def on_host_refresh(self, source_id, ip_data_dict):
        assert False


# plugin module name: plugins.wconn_*
# config file: ${ETC}/wan-connection.json
# only allow one plugin be loaded
# must set an all deny firewall rule for the out interface immediately after wan connection is up
class PluginTemplateWanConnection:

    def init2(self, tmpDir, ownResolvConf, upCallback, downCallback):
        # upCallback:
        #   is_alive() should return True in upCallback().
        #   exception raised by upCallback() would make the plugin bring down the connection.
        # downCallback:
        #   is_alive() should return False in downCallback().
        #   no exception is allowed in downCallback().
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def is_connected(self):
        assert False

    def get_ip(self):
        assert False

    def get_interface(self):
        assert False

    def get_prefix_list(self):
        # returns [(ip, mask), (ip,mask ), ...]
        assert False

    def interface_appear(self, ifname):
        # return True means we take this interface
        # must be called after start()
        assert False

    def interface_disappear(self, ifname):
        # must be called after start()
        assert False

# plugin module name: plugins.lif_*
# config file: ${ETC}/lan-interface-(PLUGIN_NAME)-(INSTANCE_NAME).json
# allow multiple plugins be loaded, and one plugin can have multiple instances


class TemplatePluginLanInterface:

    def init2(self, instanceName, cfg, tmpDir, varDir):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def interface_appear(self, bridge, ifname):
        # return True means we take this interface
        # must be called after start()
        assert False

    def interface_disappear(self, ifname):
        # must be called after start()
        assert False


# plugin module name: plugins.vpns_*
# config file: ${ETC}/vpn-server-(PLUGIN_NAME)-(INSTANCE_NAME).json
# allow multiple plugins be loaded, and one plugin can have multiple instances
class TemplatePluginVpnServer:

    def init2(self, instanceName, cfg, tmpDir, varDir, bridgePrefix, l2DnsPort, clientAddCallback, clientChangeCallback, clientRemoveCallback):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_bridge(self):
        # must be called after start()
        assert False

    def get_wan_service(self):
        assert False

    def generate_client_script(self, wan_ip, os_type):
        # returns (suggested-script-filename, script-content)
        assert False


# plugin module name: plugins.manager_*
# config file: ${ETC}/manager-(PLUGIN_NAME).json
# manager unload is not supported, so manager_disappear() is not needed
class TemplatePluginManager:

    def init2(self, cfg, etcDir, tmpDir, varDir, pluginManagerData):
        assert False

    def manager_appear(self, name, manager):
        assert False


class TemplatePluginManagerData:

    @property
    def uuid(self):
        assert False

    @property
    def prefix_pool(self):
        assert False

    @property
    def managet_caller(self):
        assert False

    @property
    def traffic_manager(self):
        assert False

    @property
    def wan_manager(self):
        assert False

    @property
    def lan_manager(self):
        assert False


# template for json object
class TemplateFacilityNameserver:

    @property
    def facility_name(self):
        assert False

    @property
    def facility_type(self):
        return "nameserver"

    @property
    def target(self):
        """[(hostname,port)]"""
        assert False

    @property
    def domain_list(self):
        assert False


# template for json object
class TemplateFacilityGateway:

    @property
    def facility_name(self):
        assert False

    @property
    def facility_type(self):
        return "gateway"

    @property
    def target(self):
        """(next-hop,interface), invalid if both is None"""
        assert False

    @property
    def network_list(self):
        assert False


# template for json object
class TemplateFacilityHttpProxy:

    """HTTP/HTTPS/FTP proxy"""

    @property
    def facility_name(self):
        assert False

    @property
    def facility_type(self):
        return "http-proxy"

    @property
    def target(self):
        """{"http":(hostname, port),"https":(hostname,port),"ftp":(hostname,port)}"""
        assert False

    @property
    def domain_list(self):
        assert False


# template for json object
class TemplateLanService:

    @property
    def protocol(self):
        assert False

    @property
    def port(self):
        assert False

    @property
    def txt_dict(self):
        assert False


# template for json object
class TemplateWanService:

    @property
    def firewall_allow_list(self):
        assert False
