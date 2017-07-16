#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import uuid
import glob
import fcntl
import json
import random
import ipaddress
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

    @staticmethod
    def getWanConnectionPluginList(param):
        return WrtCommon._getPluginList(param, "wconn")

    @staticmethod
    def getWanConnectionPlugin(param, name):
        ret = WrtCommon._getPlugin(param, "wconn", name, "")
        if ret is None:
            raise Exception("wan connection type plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def getCascadeVpnPluginList(param):
        return WrtCommon._getPluginList(param, "wvpn")

    @staticmethod
    def getCascadeVpnPlugin(param, name):
        ret = WrtCommon._getPlugin(param, "wvpn", name, "")
        if ret is None:
            raise Exception("wan vpn plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def getLanInterfacePluginList(param):
        return WrtCommon._getPluginList(param, "lif")

    @staticmethod
    def getLanInterfacePlugin(param, name, instanceName):
        ret = WrtCommon._getPlugin(param, "lif", name, instanceName)
        if ret is None:
            raise Exception("lan interface plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def getVpnServerPluginList(param):
        return WrtCommon._getPluginList(param, "vpns")

    @staticmethod
    def getVpnServerPlugin(param, name, instanceName):
        ret = WrtCommon._getPlugin(param, "vpns", name, instanceName)
        if ret is None:
            raise Exception("vpn server plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def _getPluginList(param, prefix):
        ret = []
        for fn in glob.glob(os.path.join(param.libDir, "plugins", prefix + "_*")):
            modname = fn
            modname = modname[len(param.libDir + "/"):]
            modname = modname.replace("/", ".")
            exec("import %s" % (modname))
            ret += eval("%s.get_plugin_list()" % (modname))
        return ret

    @staticmethod
    def _getPlugin(param, prefix, name, instance_name):
        for fn in glob.glob(os.path.join(param.libDir, "plugins", prefix + "_*")):
            modname = fn
            modname = modname[len(param.libDir + "/"):]
            modname = modname.replace("/", ".")
            exec("import %s" % (modname))
            if name in eval("%s.get_plugin_list()" % (modname)):
                obj = eval("%s.get_plugin(\"%s\")" % (modname, name))
                if instance_name != "":
                    obj.full_name = name + "-" + instance_name
                else:
                    obj.full_name = name
                return obj
        return None


class Managers:

    _param = None
    _callRecord = dict()

    @staticmethod
    def init(param):
        Managers._param = param
        Managers._callRecord["traffic"] = dict()
        Managers._callRecord["wan"] = dict()
        Managers._callRecord["lan"] = dict()
        Managers._callRecord["cascade"] = dict()
        Managers._callRecord["sgw"] = dict()

    @staticmethod
    def call(funcName, *args):
        Managers._callFunc("traffic", Managers._param.trafficManager, funcName, *args)
        Managers._callFunc("wan", Managers._param.wanManager, funcName, *args)
        Managers._callFunc("lan", Managers._param.lanManager, funcName, *args)
        Managers._callFunc("cascade", Managers._param.cascadeManager, funcName, *args)
        Managers._callFunc("sgw", Managers._param.sgwManager, funcName, *args)

    @staticmethod
    def _callFunc(objName, obj, funcName, *args):
        if obj is None:
            return

        if funcName.endswith("_down"):
            upFuncName = re.sub("_down$", "_up", funcName)
            if upFuncName not in Managers._callRecord[objName]:
                return
            if hasattr(obj, funcName):
                getattr(obj, funcName)(*args)
            del Managers._callRecord[objName][upFuncName]
        else:
            if hasattr(obj, funcName):
                getattr(obj, funcName)(*args)
            if funcName.endswith("_up"):
                Managers._callRecord[objName][funcName] = True


class DnsMasqHostFilesLock:

    def __init__(self, tmpDir):
        self.lockFile = os.path.join(tmpDir, "hosts.d", ".lock")
        self.lockFd = None

    def __enter__(self):
        try:
            self.lockFd = os.open(self.lockFile, os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC, 0o600)
            fcntl.lockf(self.lockFd, fcntl.LOCK_EX)
        except BaseException:
            if self.lockFd is not None:
                os.close(self.lockFd)
                self.lockFd = None

    def __exit__(self, *_):
        os.close(self.lockFd)
        self.lockFd = None


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

    def get_subhost_ip_range(self):
        # return list(start_ip, end_ip)
        assert False

    def on_source_add(self, source_id):
        pass

    def on_source_remove(self, source_id):
        pass

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


# plugin module name: plugins.wvpn_*
# config file: ${ETC}/cascade-vpn.json
# only allow one plugin be loaded
class PluginTemplateCascadeVpn:

    def init2(self, cfg, tmpDir, upCallback, downCallback):
        # upCallback:
        #   is_connected() should return True in upCallback().
        #   exception raised by upCallback() would make the plugin bring down the connection.
        # downCallback:
        #   is_connected() should return False in downCallback().
        #   no exception is allowed in downCallback().
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def disconnect(self):
        assert False

    def is_connected(self):
        assert False

    def get_local_ip(self):
        assert False

    def get_remote_ip(self):
        assert False

    def get_netmask(self):
        assert False

    def get_interface(self):
        assert False

    def get_prefix_list(self):
        # returns [(ip, mask), (ip,mask ), ...]
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

    def init2(self, instanceName, cfg, tmpDir, varDir, bridgePrefix, l2DnsPort, clientAddOrChangeCallback, clientRemoveCallback, firewallAllowFunc):
        assert False

    def set_other_bridge_list(self, bridge_list):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_bridge(self):
        # must be called after start()
        assert False

    def generate_client_script(self, wan_ip, os_type):
        # returns (suggested-script-filename, script-content)
        assert False


class TemplateTrafficManagementData:

    @property
    def domain_ip_dict(self):
        # dict<domain-name, ip-address>, optional
        assert False

    @property
    def domain_nameserver_dict(self):
        # dict<domain-name, nameserver-list>, optional
        assert False

    @property
    def web_transparent_proxy_dict(self):
        # dict<url-source, url-target>, optional
        assert False

    @property
    def route_dict(self):
        # dict<prefix, (nexthop, interface)>, optional
        assert False

    @property
    def firewall_allow(self):
        # list<rule>, optional
        assert False

    @property
    def firewall_port_mapping_dict(self):
        # dict<port, (ip, port)>, optional
        assert False
