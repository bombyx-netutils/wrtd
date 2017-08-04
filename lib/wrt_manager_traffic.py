#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import logging
import ipaddress
import subprocess
from wrt_util import WrtUtil


class WrtTrafficManager:

    def __init__(self, param):
        self.param = param
        self.cfgFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.conf")
        self.pidFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.pid")
        self.logger = logging.getLogger(self.__module__ + "." + self.__class__.__name__)

        self.wanServDict = dict()               # dict<name,json-object>

        self.routeFullDict = _RouteFullDict()
        self.routeDict = dict()
        self.routeRefreshInterval = 10          # 10 seconds
        self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routerRefresh)

        self.domainNameserverFullDict = _DomainNameServerFullDict()
        self.domainIpFullDict = _DomainIpFullDict()

        self.dnsPort = None
        self.dnsmasqProc = None
        try:
            self._runDnsmasq()
            self.logger.info("Level 2 nameserver started.")

            GLib.add
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

        # record
        self.tfacGroupDict[name] = _TrafficFacilityGroup()
        self.tfacGroupDict[name].priority = priority
        self.tfacGroupDict[name].facility_list = facility_list

        # trigger route refresh
        GLib.source_remove(self.routeRefreshTimer)
        self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routerRefresh)

    def change_tfac_group(self, name, facility_list):
        assert name in self.tfacGroupDict:

        # record
        self.tfacGroupDict[name].facility_list = facility_list

        # trigger route refresh
        GLib.source_remove(self.routeRefreshTimer)
        self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routerRefresh)

    def remove_tfac_group(self, name):
        # record
        del self.tfacGroupDict[name]

        # trigger route refresh
        GLib.source_remove(self.routeRefreshTimer)
        self.routeRefreshTimer = GObject.timeout_add_seconds(0, self._routerRefresh)

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

    def _trafficFacilityListToRouteFullDict(name, priority, facility_list):
        newRouteFullDict = self.routeFullDict.copy()
        ret.remove_route_by_name(name)

        for item in facility_list:
            if item["facility-type"] == "gateway":
                for prefix in item["network-list"]:
                    ret.add_route(name, priority, prefix, item["target"][0], item["target"][1])

        return ret

    def _routeRefresh(self):
        try:
            newRouteDict = self.routeFullDict.get_route_dict()

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
            self.routeRefreshTimer = GObject.timeout_add_seconds(self.routeRefreshInterval, self._routerRefresh)
            return False


class _RouteFullDict:

    def __init__(self):
        self.dictImpl = dict()

    def copy(self):
        ret = _RouteFullDict()
        ret.dictImpl = copy.deepcopy(self.dictImpl)
        return ret

    def add_route(self, name, priority, prefix, nexthop, interface):
        if prefix not in self.dictImpl:
            self.dictImpl[prefix] = dict()
        if priority not in self.dictImple[prefix]:
            self.dictImpl[prefix][priority] = dict()
        assert name not in self.dictImpl[prefix][priority]
        self.dictImpl[prefix][priority][name] = (nexthop, interface)

    def remove_route_by_name(self, name):
        for prefix in list(self.dictImpl.keys()):
            for priority in list(self.dictImpl[prefix].keys()):
                if name in self.dictImpl[prefix][priority]:
                    del self.dictImpl[prefix][priority][name]
                    if len(self.dictImpl[prefix][priority]) == 0:
                        del self.dictImpl[prefix][priority]
                        if len(self.dictImpl[prefix]) == 0:
                            del self.dictImpl[prefix]

    def get_route_dict(self):
        ret = dict()
        for prefix, data in self.dictImpl.items():
            priority = sorted(list(self.dictImpl[prefix].keys()))[0]
            name = sorted(list(self.dictImpl[prefix][priority].keys()))[0]
            ret[prefix] = self.dictImpl[prefix][priority][name]
        return ret


class _Helper:

    @staticmethod
    def updateRoute(self.routeDict, newRouteDict):







            tlist = list(self.routesDict[gateway_ip][router_id])
            for prefix in tlist:
                if prefix not in prefix_list:


            # add routes
            for prefix in prefix_list:
                if prefix not in self.routesDict[gateway_ip][router_id]:
                    ipp.route("add", dst=self.prefixConvert(prefix), gateway=gateway_ip)
                    self.routesDict[gateway_ip][router_id].append(prefix)

        pass

    @staticmethod
    def prefixConvert(self, prefix):
        tl = prefix.split("/")
        return tl[0] + "/" + str(util.ipMaskToLen(tl[1]))


























        # # add nat rule
        # subprocess.check_call(["/sbin/nft", "add", "table", "ip", "cgfw"])
        # subprocess.check_call(["/sbin/nft", "add", "chain", "cgfw", "fw", "{", "type", "filter", "hook", "prerouting", "priority", "0", ";", "}"])
        # subprocess.check_call(["/sbin/nft", "add", "chain", "cgfw", "natpre", "{", "type", "nat", "hook", "prerouting", "priority", "0", ";", "}"])
        # subprocess.check_call(["/sbin/nft", "add", "chain", "cgfw", "natpost", "{", "type", "nat", "hook", "postrouting", "priority", "0", ";", "}"])
        # subprocess.check_call(["/sbin/nft", "add", "rule", "cgfw", "fw", "iifname", "\"cgfw\"", "ct", "state", "established,related", "accept"])
        # subprocess.check_call(["/sbin/nft", "add", "rule", "cgfw", "fw", "iifname", "\"cgfw\"", "ip", "protocol", "icmp", "accept"])
        # subprocess.check_call(["/sbin/nft", "add", "rule", "cgfw", "fw", "iifname", "\"cgfw\"", "drop"])
        # subprocess.check_call(["/sbin/nft", "add", "rule", "cgfw", "natpost", "oifname", "\"cgfw\"", "masquerade"])




