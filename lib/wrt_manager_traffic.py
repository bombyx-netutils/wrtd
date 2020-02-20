#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import logging
import pyroute2
import subprocess
import iptc
from gi.repository import GLib
from gi.repository import GObject
from wrt_util import WrtUtil


class WrtTrafficManager:

    def __init__(self, param):
        self.param = param
        self.cfgFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.conf")
        self.pidFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.pid")
        self.hostsDir = os.path.join(self.param.tmpDir, "l2-dnsmasq.hosts.d")
        self.logger = logging.getLogger(self.__module__ + "." + self.__class__.__name__)

        self.wanServDict = dict()               # dict<name,json-object>

        self.tfacGroupDict = dict()             # dict<name, priority>

        self.routeFullDict = _NamePriorityKeyValueDict()
        self.routeDict = dict()                 # dict<prefix, data>
        self.gatewayDict = dict()               # dict<name, set<interface>>

        self.domainNameserverFullDict = _NamePriorityKeyValueDict()
        self.domainNameserverDict = dict()

        self.domainIpFullDict = _NamePriorityKeyValueDict()

        self.routeRefreshInterval = 10               # 10 seconds
        self.routeRefreshTimer = GObject.timeout_add_seconds(self.routeRefreshInterval, self._routeRefreshTimerCallback)

        self.dnsPort = WrtUtil.getFreeSocketPort("tcp")
        self.dnsmasqProc = None
        try:
            self._runDnsmasq()
            self.logger.info("Level 2 nameserver started.")
        except BaseException:
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

        ret = self._trafficFacilityListToRouteFullDict(name, priority, facility_list)
        if len(ret) > 0:
            GLib.source_remove(self.routeRefreshTimer)
            self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routeRefreshTimerCallback)

        gatewaySet = self._getGatewaySetFromTrafficFacilityList(facility_list)
        self._addGatewayFwRules(gatewaySet)
        self.gatewayDict[name] = gatewaySet

        ret = self._trafficFacilityListToDomainNameserverFullDict(name, priority, facility_list)
        if len(ret) > 0:
            self._stopDnsmasq()
            self._runDnsmasq()

    def change_tfac_group(self, name, facility_list):
        assert name in self.tfacGroupDict

        ret1 = self.routeFullDict.remove_by_name(name)
        ret2 = self._trafficFacilityListToRouteFullDict(name, self.tfacGroupDict[name], facility_list)
        if ret1 != ret2:
            GLib.source_remove(self.routeRefreshTimer)
            self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routeRefreshTimerCallback)

        gatewaySet = self._getGatewaySetFromTrafficFacilityList(facility_list)
        self._removeGatewayFwRules(self.gatewayDict[name] - gatewaySet)
        self._addGatewayFwRules(gatewaySet - self.gatewayDict[name])
        self.gatewayDict[name] = gatewaySet

        ret1 = self.domainNameserverFullDict.remove_by_name(name)
        ret2 = self._trafficFacilityListToDomainNameserverFullDict(name, self.tfacGroupDict[name], facility_list)
        if ret1 != ret2:
            self._stopDnsmasq()
            self._runDnsmasq()

    def remove_tfac_group(self, name):
        del self.tfacGroupDict[name]

        ret = self.routeFullDict.remove_by_name(name)
        if len(ret) > 0:
            GLib.source_remove(self.routeRefreshTimer)
            self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routeRefreshTimerCallback)

        self._removeGatewayFwRules(self.gatewayDict[name])
        del self.gatewayDict[name]

        ret = self.domainNameserverFullDict.remove_by_name(name)
        if len(ret) > 0:
            self._stopDnsmasq()
            self._runDnsmasq()

    def on_wan_conn_up(self):
        rule = iptc.Rule()
        rule.out_interface = self.param.wanManager.wanConnPlugin.get_interface()
        rule.create_target("MASQUERADE")
        iptc.Chain(iptc.Table(iptc.Table.NAT), "POSTROUTING").insert_rule(rule)        # this rule would be auto deleted when WAN conection is down

        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s ct state established,related accept' % (intf))
        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s ip protocol icmp accept' % (intf))
        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s drop' % (intf))

    def _dispose(self):
        self._stopDnsmasq()

    def _runDnsmasq(self):
        # make hosts directory
        os.mkdir(self.hostsDir)

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
        buf += "\n"
        buf += "no-hosts\n"
        buf += "addn-hosts=%s\n" % (self.hostsDir)                       # "hostsdir=" only adds record, no deletion, so not usable
        buf += "\n"
        buf += "resolv-file=%s\n" % (self.param.ownResolvConf)
        for domain, nsList in self.domainNameserverFullDict.get_dict().items():
            for ns in nsList:
                buf += "server=/%s/%s\n" % (domain, ns.replace(":", "#"))
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
        WrtUtil.forceDelete(self.hostsDir)
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
        ret = set()
        for item in facility_list:
            if item["facility-type"] == "gateway":
                for prefix in item["network-list"]:
                    self.routeFullDict.set_key_value(name, priority, prefix, item["target"])
                    ret.add(prefix)
        return ret

    def _trafficFacilityListToDomainNameserverFullDict(self, name, priority, facility_list):
        ret = set()
        for item in facility_list:
            if item["facility-type"] == "nameserver":
                for domain in item["domain-list"]:
                    self.domainNameserverFullDict.set_key_value(name, priority, domain, item["target"])
                    ret.add(domain)
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
                            if e.code == 3:     # message: No such process
                                pass            # route does not exist, ignore
                            else:
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
                        if e.code == 17:                    # message: File exists
                            del newRouteDict[prefix]        # route already exists, retry in next cycle
                        elif e.code == 101:                 # message: Network is unreachable
                            del newRouteDict[prefix]        # nexthop is invalid, retry in next cycle
                        else:
                            raise
            self.routeDict = newRouteDict
        except Exception:
            self.logger.error("Error occured in route refresh timer callback", exc_info=True)
        finally:
            self.routeRefreshTimer = GObject.timeout_add_seconds(self.routeRefreshInterval, self._routeRefreshTimerCallback)
            return False

    def _addGatewayFwRules(self, gatewaySet):
        filterTable = iptc.Table(iptc.Table.FILTER)
        natTable = iptc.Table(iptc.Table.NAT)
        filterTable.autocommit = False
        natTable.autocommit = False
        try:
            for gateway in gatewaySet:
                for rule in self.__generateGatewayFwRulesFilterInputChain(gateway):
                    iptc.Chain(filterTable, "INPUT").append_rule(rule)
                for rule in self.__generateGatewayFwRulesNatPostChain(gateway):
                    iptc.Chain(natTable, "POSTROUTING").append_rule(rule)
            filterTable.commit()
            natTable.commit()
        finally:
            filterTable.autocommit = True
            natTable.autocommit = True

    def _removeGatewayFwRules(self, gatewaySet):
        filterTable = iptc.Table(iptc.Table.FILTER)
        natTable = iptc.Table(iptc.Table.NAT)
        filterTable.autocommit = False
        natTable.autocommit = False
        try:
            for gateway in gatewaySet:
                for rule in self.__generateGatewayFwRulesFilterInputChain(gateway):
                    iptc.Chain(filterTable, "INPUT").delete_rule(rule)
                for rule in self.__generateGatewayFwRulesNatPostChain(gateway):
                    iptc.Chain(natTable, "POSTROUTING").delete_rule(rule)
            filterTable.commit()
            natTable.commit()
        finally:
            filterTable.autocommit = True
            natTable.autocommit = True

    def __generateGatewayFwRulesFilterInputChain(self, gateway):
        ret = []

        rule = iptc.Rule()
        rule.in_interface = gateway
        rule.protocol = "icmp"
        rule.create_target("ACCEPT")
        ret.append(rule)

        rule = iptc.Rule()
        rule.in_interface = gateway
        match = iptc.Match(rule, "state")
        match.state = "ESTABLISHED,RELATED"
        rule.add_match(match)
        rule.create_target("ACCEPT")
        ret.append(rule)

        rule = iptc.Rule()
        rule.in_interface = gateway
        rule.create_target("DROP")
        ret.append(rule)

        return ret

    def __generateGatewayFwRulesNatPostChain(self, gateway):
        rule = iptc.Rule()
        rule.out_interface = gateway
        rule.create_target("MASQUERADE")
        return [rule]


class _NamePriorityKeyValueDict:

    def __init__(self):
        self.dictImpl = dict()

    def set_key_value(self, name, priority, key, value):
        if key not in self.dictImpl:
            self.dictImpl[key] = dict()
        if priority not in self.dictImpl[key]:
            self.dictImpl[key][priority] = dict()
        self.dictImpl[key][priority][name] = value

    def remove_by_name(self, name):
        ret = set()
        for key in list(self.dictImpl.keys()):
            for priority in list(self.dictImpl[key].keys()):
                if name in self.dictImpl[key][priority]:
                    del self.dictImpl[key][priority][name]
                    ret.add(key)
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
    def prefixConvert(prefix):
        tl = prefix.split("/")
        return tl[0] + "/" + str(WrtUtil.ipMaskToLen(tl[1]))
