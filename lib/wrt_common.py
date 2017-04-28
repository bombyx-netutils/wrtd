#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
import fcntl
import json
import ipaddress


class WrtCommon:

    @staticmethod
    def bridgeGetIp(bridge):
        return str(ipaddress.IPv4Address(bridge.get_prefix()[0]) + 1)

    @staticmethod
    def getWanConnectionPluginList(param):
        return WrtCommon._getPluginList(param, "wconn")

    @staticmethod
    def getWanConnectionPlugin(param, name):
        ret = WrtCommon._getPlugin(param, "wconn", name)
        if ret is None:
            raise Exception("wan connection type plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def getWanVpnPluginList(param):
        return WrtCommon._getPluginList(param, "wvpn")

    @staticmethod
    def getWanVpnPlugin(param, name):
        ret = WrtCommon._getPlugin(param, "wvpn", name)
        if ret is None:
            raise Exception("wan vpn plugin %s does not exists" % (name))
        return ret

    @staticmethod
    def getLanInterfacePluginList(param):
        return WrtCommon._getPluginList(param, "lif")

    @staticmethod
    def getLanInterfacePlugin(param, name):
        ret = WrtCommon._getPlugin(param, "lif", name)
        if ret is None:
            raise Exception("lan interface plugin %s does not exists" % (name))
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
    def _getPlugin(param, prefix, name):
        for fn in glob.glob(os.path.join(param.libDir, "plugins", prefix + "_*")):
            modname = fn
            modname = modname[len(param.libDir + "/"):]
            modname = modname.replace("/", ".")
            exec("import %s" % (modname))
            if name in eval("%s.get_plugin_list()" % (modname)):
                return eval("%s.get_plugin(\"%s\")" % (modname, name))
        return None


class DnsMasqHostFilesLock:

    def __init__(self, tmpDir):
        self.lockFile = os.path.join(tmpDir, "hosts.d", ".lock")
        self.lockFd = None

    def __enter__(self):
        try:
            self.lockFd = os.open(self.lockFile, os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC, 0o600)
            fcntl.lockf(self.lockFd, fcntl.LOCK_EX)
        except:
            if self.lockFd is not None:
                os.close(self.lockFd)
                self.lockFd = None

    def __exit__(self, *_):
        os.close(self.lockFd)
        self.lockFd = None


class PrefixPool:

    def __init__(self, dataFile):
        self.dataFile = dataFile
        self.upstreamPrefixList = []    # list<prefix-ip, prefix-mask>
        self.prefixList = []            # list<prefix-ip, prefix-mask, used-flag>
        self._load()

    def setUpstreamPrefixList(self, upstreamPrefixList):
        ret = False

        # get conflict items
        idxList = []
        for i in range(0, len(self.prefixList)):
            pip, pmask, used = self.prefixList[i]
            netobj = ipaddress.IPv4Network(pip + "/" + pmask)
            for ip2, mask2 in upstreamPrefixList:
                if netobj.overlaps(ipaddress.IPv4Network(ip2 + "/" + mask2)):
                    idxList.append(i)
                    if used:
                        ret = True              # program restart needed
                    break

        # get a reference list for create new prefix
        refList = []
        for i in range(0, len(self.prefixList)):
            if i not in idxList:
                refList.append(self.prefixList[i])

        # create new prefix for conflict items
        for i in idxList:
            pip, pmask = PrefixPool._createNewPrefix(refList + upstreamPrefixList)
            self.prefixList[i] = (pip, pmask, False)

        self.upstreamPrefixList = upstreamPrefixList
        self._save()
        return ret

    def usePrefix(self):
        # use a prefix in pool
        for i in range(0, len(self.prefixList)):
            ip, mask, used = self.prefixList[i]
            if not used:
                self.prefixList[i] = (ip, mask, True)
                return (ip, mask)

        # create a new prefix
        pip, pmask = PrefixPool._createNewPrefix(self.prefixList + self.upstreamPrefixList)
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

    @staticmethod
    def _createNewPrefix(excludeList):
        pip = None
        pmask = None
        for i in range(0, 256):
            pip = "192.168.%d.0" % (i)
            pmask = "255.255.255.0"
            overlap = False
            netobj = ipaddress.IPv4Network(pip + "/" + pmask)
            for item in excludeList:
                ip2 = item[0]
                mask2 = item[1]
                if netobj.overlaps(ipaddress.IPv4Network(ip2 + "/" + mask2)):
                    overlap = True
                    break
            if overlap:
                continue
            break
        assert pip is not None and pmask is not None
        return (pip, pmask)


class TemplateBridge:

    def init2(self, brname, prefix, l2DnsPort, clientAppearFunc, clientChangeFunc, clientDisappearFunc):
        assert False

    def dispose(self):
        assert False

    def get_name(self):
        assert False

    def get_prefix(self):
        assert False

    def get_bridge_id(self):
        assert False

    def get_subhost_ip_range(self):
        # return list(start_ip, end_ip)
        assert False

    def on_other_bridge_created(self, ip):
        assert False

    def on_other_bridge_destroyed(self, ip):
        assert False

    def on_upstream_connected(self, ip):
        assert False

    def on_upstream_disconnected(self, ip):
        assert False

    def on_host_appear(self, sourceId, ipDataDict):
        assert False

    def on_host_disappear(self, sourceId, ipList):
        assert False

    def on_host_refresh(self, sourceId, ipDataDict):
        assert False


# plugin module name: plugins.wconn_*
# config file: ${ETC}/wan-connection.json
# only allow one plugin be loaded
class PluginTemplateWanConnection:

    def init2(self, tmpDir, ownResolvConf):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_out_interface(self):
        assert False

    def interface_appear(self, ifname):
        # return True means we take this interface
        # must be call after start()
        assert False

    def interface_disappear(self, ifname):
        # must be call after start()
        assert False


# plugin module name: plugins.wvpn_*
# config file: ${ETC}/wan-vpn.json
# only allow one plugin be loaded
class PluginTemplateWanVpn:

    def init2(self, tmpDir):
        assert False

    def start(self, cfg):
        assert False

    def stop(self):
        assert False

    def is_alive(self):
        assert False

    def get_local_ip(self):
        assert False

    def get_remote_ip(self):
        assert False

    def get_netmask(self):
        assert False

    def get_interface(self):
        assert False


# plugin module name: plugins.lif_*
# config file: ${ETC}/lan-interface-(PLUGIN_NAME)-(INSTANCE_NAME).json
# allow multiple plugins be loaded, and one plugin can have multiple instances
class TemplatePluginLanInterface:

    def init2(self, instanceName, cfg, tmpDir):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_bridge(self):
        # return None means using default bridge
        # must be call after start()
        assert False

    def interface_appear(self, bridge, ifname):
        # return True means we take this interface
        # must be call after start()
        assert False

    def interface_disappear(self, ifname):
        # must be call after start()
        assert False
