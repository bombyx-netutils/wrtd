#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import logging
import pyroute2
import subprocess
from gi.repository import GLib
from gi.repository import GObject
from wrt_util import WrtUtil


class WrtTrafficManager:

    def __init__(self, param):
        self.param = param
        self.cfgFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.conf")
        self.pidFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.pid")
        self.logger = logging.getLogger(self.__module__ + "." + self.__class__.__name__)

        self.wanServDict = dict()               # dict<name,json-object>

        self.tfacGroupDict = dict()             # dict<name, priority>

        self.routeFullDict = _NamePriorityKeyValueDict()
        self.routeDict = dict()                 # real route dict

        self.gatewayDict = dict()               # dict<name, set<interface>>

        self.domainNameserverFullDict = _NamePriorityKeyValueDict()

        self.domainIpFullDict = _NamePriorityKeyValueDict()

        self.routeRefreshInterval = 10               # 10 seconds
        self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routeRefreshTimerCallback)

        self.dnsPort = None
        self.dnsmasqProc = None
        try:
            self._runDnsmasq()
            self.logger.info("Level 2 nameserver started.")
        except:
            self._dispose()
            raise

    def dispose(self):
        self._dispose()
        self.logger.info("Terminated.")

    def get_l2_nameserver_port(self):
        return self.dnsPort

    def has_wan_service(self, name):
        return name in self.wanServDict

    def add_wan_service(self, name, service):
        assert name not in self.wanServDict
        self.wanServDict[name] = service

    def remove_wan_service(self, name):
        del self.wanServDict[name]

    def has_tfac_group(self, name):
        return name in self.tfacGroupDict

    def add_tfac_group(self, name, priority, facility_list):
        assert name not in self.tfacGroupDict

        self.tfacGroupDict[name] = priority

        if self._trafficFacilityListToRouteFullDict(name, priority, facility_list):
            GLib.source_remove(self.routeRefreshTimer)
            self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routeRefreshTimerCallback)

        gatewaySet = self._getGatewaySetFromTrafficFacilityList(facility_list)
        self._addGatewayNftRules(gatewaySet)
        self.gatewayDict[name] = gatewaySet

        if self._trafficFacilityListToDomainNameserverFullDict(name, priority, facility_list):
            pass

    def change_tfac_group(self, name, facility_list):
        assert name in self.tfacGroupDict

        ret = False
        ret |= self.routeFullDict.remove_by_name(name)
        ret |= self._trafficFacilityListToRouteFullDict(name, self.tfacGroup[name], facility_list)
        if ret:
            GLib.source_remove(self.routeRefreshTimer)
            self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routeRefreshTimerCallback)

        gatewaySet = self._getGatewaySetFromTrafficFacilityList(facility_list)
        self._removeGatewayNftRules(self.gatewayDict[name] - gatewaySet)
        self._addGatewayNftRules(gatewaySet - self.gatewayDict[name])
        self.gatewayDict[name] = gatewaySet

        ret = False
        ret |= self.domainNameserverFullDict.remove_by_name(name)
        ret |= self._trafficFacilityListToDomainNameserverFullDict(name, self.tfacGroup[name], facility_list)
        if ret:
            pass

    def remove_tfac_group(self, name):
        del self.tfacGroupDict[name]

        if self.routeFullDict.remove_by_name(name):
            GLib.source_remove(self.routeRefreshTimer)
            self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routeRefreshTimerCallback)

        self._removeGatewayNftRules(self.gatewayDict[name])
        del self.gatewayDict[name]

        if self.domainNameserverFullDict.remove_by_name(name):
            pass

    def on_wan_conn_up(self):
        WrtUtil.shell('/sbin/nft add rule wrtd natpost oifname %s masquerade' % (self.param.wanManager.wanConnPlugin.get_interface()))
        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s ct state established,related accept' % (intf))
        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s ip protocol icmp accept' % (intf))
        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s drop' % (intf))

    def _dispose(self):
        self._stopDnsmasq()

    def _runDnsmasq(self):
        self.dnsPort = WrtUtil.getFreeSocketPort("tcp")

        # generate dnsmasq config file
        buf = ""
        buf += "strict-order\n"
        buf += "bind-interfaces\n"                            # don't listen on 0.0.0.0
        buf += "interface=lo\n"
        buf += "user=root\n"
        buf += "group=root\n"
        buf += "\n"
        buf += "domain-needed\n"
        buf += "bogus-priv\n"
        buf += "no-hosts\n"
        buf += "resolv-file=%s\n" % (self.param.ownResolvConf)
        buf += "\n"
        with open(self.cfgFile, "w") as f:
            f.write(buf)

        # run dnsmasq process
        cmd = "/usr/sbin/dnsmasq"
        cmd += " --keep-in-foreground"
        cmd += " --port=%d" % (self.dnsPort)
        cmd += " --conf-file=\"%s\"" % (self.cfgFile)
        cmd += " --pid-file=%s" % (self.pidFile)
        self.dnsmasqProc = subprocess.Popen(cmd, shell=True, universal_newlines=True)

    def _stopDnsmasq(self):
        if self.dnsmasqProc is not None:
            self.dnsmasqProc.terminate()
            self.dnsmasqProc.wait()
            self.dnsmasqProc = None
        WrtUtil.forceDelete(self.pidFile)
        WrtUtil.forceDelete(self.cfgFile)

    def _getGatewaySetFromTrafficFacilityList(self, facility_list):
        ret = set()
        for item in facility_list:
            if item["facility-type"] == "gateway":
                nexthop, interface = item["target"]
                if interface is not None:
                    ret.add(interface)
        return ret

    def _trafficFacilityListToRouteFullDict(self, name, priority, facility_list):
        ret = False
        for item in facility_list:
            if item["facility-type"] == "gateway":
                for prefix in item["network-list"]:
                    self.routeFullDict.add(name, priority, prefix, item["target"])
                    ret = True
        return ret

    def _trafficFacilityListToDomainNameserverFullDict(self, name, priority, facility_list):
        ret = False
        for item in facility_list:
            if item["facility-type"] == "nameserver":
                for domain in item["domain-list"]:
                    self.domainNameserverFullDict.add(name, priority, domain, item["target"])
                    ret = True
        return ret

    def _trafficFacilityListToDomainIpFullDict(self, name, priority, facility_list):
        assert False
        return False

    def _routeRefreshTimerCallback(self):
        try:
            newRouteDict = self.routeFullDict.get_dict()

            with pyroute2.IPRoute() as ipp:
                # remove routes
                for prefix in self.routeDict:
                    if prefix not in newRouteDict:
                        try:
                            ipp.route("del", dst=_Helper.prefixConvert(prefix))
                        except pyroute2.netlink.exceptions.NetlinkError as e:
                            if e[0] == 3 and e[1] == "No such process":
                                pass        # route does not exist, ignore this error
                            raise

                # add or change routes
                for prefix, data in list(newRouteDict.items()):
                    nexthop, interface = data
                    if interface is not None:
                        idx_list = ipp.link_lookup(ifname=interface)
                        if idx_list == []:
                            del newRouteDict[prefix]
                            continue
                        assert len(idx_list) == 1
                        idx = idx_list[0]

                    try:
                        if prefix not in self.routeDict:                                    # add
                            if nexthop is not None and interface is not None:
                                ipp.route("add", dst=_Helper.prefixConvert(prefix), gateway=nexthop, oif=idx)
                            elif nexthop is not None and interface is None:
                                ipp.route("add", dst=_Helper.prefixConvert(prefix), gateway=nexthop)
                            elif nexthop is None and interface is not None:
                                ipp.route("add", dst=_Helper.prefixConvert(prefix), oif=idx)
                            else:
                                assert False
                        else:                                                               # change
                            pass        # fixme
                    except pyroute2.netlink.exceptions.NetlinkError as e:
                        if e[0] == 101 and e[1] == "Network is unreachable":
                            del newRouteDict[prefix]        # nexthop is invalid, retry in next cycle
                            continue
                        raise

            self.routeDict = newRouteDict
        finally:
            self.routeRefreshTimer = GObject.timeout_add_seconds(self.routeRefreshInterval, self._routeRefreshTimerCallback)
            return False

    def _addGatewayNftRules(self, gatewaySet):
        for gateway in gatewaySet:
            gateway = "\"" + gateway + "\""
            subprocess.check_call(["/sbin/nft", "add", "rule", "wrtd", "fw", "iifname", gateway, "ct", "state", "established,related", "accept"])
            subprocess.check_call(["/sbin/nft", "add", "rule", "wrtd", "fw", "iifname", gateway, "ip", "protocol", "icmp", "accept"])
            subprocess.check_call(["/sbin/nft", "add", "rule", "wrtd", "fw", "iifname", gateway, "drop"])
            subprocess.check_call(["/sbin/nft", "add", "rule", "wrtd", "natpost", "oifname", gateway, "masquerade"])

    def _removeGatewayNftRules(self, gatewaySet):
        if len(gatewaySet) == 0:
            return

        msg = WrtUtil.shell('/sbin/nft list table ip wrtd -a', "stdout")
        for gateway in gatewaySet:
            for m in re.finditer("^.* \\\"%s\\\" .* # handle ([0-9]+)$" % (gateway), msg, re.M):
                # a dirty implementation
                subprocess.call(["/sbin/nft delete rule wrtd fw handle %s 2>/dev/null" % (m.group(1))], shell=True)
                subprocess.call(["/sbin/nft delete rule wrtd natpre handle %s 2>/dev/null" % (m.group(1))], shell=True)
                subprocess.call(["/sbin/nft delete rule wrtd natpost handle %s 2>/dev/null" % (m.group(1))], shell=True)


class _NamePriorityKeyValueDict:

    def __init__(self):
        self.dictImpl = dict()

    def add(self, name, priority, key, value):
        if key not in self.dictImpl:
            self.dictImpl[key] = dict()
        if priority not in self.dictImpl[key]:
            self.dictImpl[key][priority] = dict()
        assert name not in self.dictImpl[key][priority]
        self.dictImpl[key][priority][name] = value

    def remove_by_name(self, name):
        ret = False
        for key in list(self.dictImpl.keys()):
            for priority in list(self.dictImpl[key].keys()):
                if name in self.dictImpl[key][priority]:
                    del self.dictImpl[key][priority][name]
                    ret = True
                    if len(self.dictImpl[key][priority]) == 0:
                        del self.dictImpl[key][priority]
                        if len(self.dictImpl[key]) == 0:
                            del self.dictImpl[key]
        return ret

    def get_dict(self):
        ret = dict()
        for key, data in self.dictImpl.items():
            priority = sorted(list(data.keys()))[0]
            name = sorted(list(data[priority].keys()))[0]
            ret[key] = data[priority][name]
        return ret


class _Helper:

    @staticmethod
    def prefixConvert(self, prefix):
        tl = prefix.split("/")
        return tl[0] + "/" + str(WrtUtil.ipMaskToLen(tl[1]))
