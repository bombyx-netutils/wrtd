#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import json
import logging
import subprocess
import pyroute2
from wrt_util import WrtUtil
from wrt_common import WrtCommon


class WrtTrafficManager:

    def __init__(self, param):
        self.param = param
        self.cfgFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.conf")
        self.pidFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.pid")

        self.pluginList = []
        self.wanServDict = dict()           # dict<name,json-object>
        self.tfacGroupDict = dict()         # dict<name,_TrafficFacilityGroup>
        self.routesDict = dict()            # dict<gateway-ip, dict<router-id, list<prefix>>>

        self.dnsPort = None
        self.dnsmasqProc = None
        try:
            self._runDnsmasq()
            logging.info("Level 2 nameserver started.")

            # start all traffic plugins
            for name in WrtCommon.getTrafficPluginList(self.param):
                fn = os.path.join(self.param.etcDir, "traffic-%s.json" % (name))
                if not os.path.exists(fn):
                    continue

                tmpdir = os.path.join(self.param.tmpDir, name)
                os.mkdir(tmpdir)

                vardir = os.path.join(self.param.varDir, name)
                WrtUtil.ensureDir(vardir)

                if os.path.getsize(fn) > 0:
                    with open(fn, "r") as f:
                        cfgObj = json.load(f)
                else:
                    cfgObj = dict()

                p = WrtCommon.getTrafficPlugin(self.param, name)
                p.init2(cfgObj, tmpdir, vardir)
                p.start()
                self.pluginList.append(p)
                logging.info("Traffic plugin \"%s\" activated." % (p.full_name))
        except BaseException:
            self.dispose()
            raise

    def dispose(self):
        self._dispose()
        logging.info("Terminated.")

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

    def add_tfac_group(self, name, priority, tfac_group):
        assert name not in self.tfacGroupDict
        self.tfacGroupDict[name] = _TrafficFacilityGroup()
        self.tfacGroupDict[name].priority = priority
        self.tfacGroupDict[name].facility_list = tfac_group

    def change_tfac_group(self, name, tfac_group):
        self.tfacGroupDict[name].facility_list = tfac_group

    def remove_tfac_group(self, name):
        del self.tfacGroupDict[name]

    def on_wconn_up(self):
        WrtUtil.shell('/sbin/nft add rule wrtd natpost oifname %s masquerade' % (self.param.wanManager.wanConnPlugin.get_interface()))
        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s ct state established,related accept' % (intf))
        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s ip protocol icmp accept' % (intf))
        # WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s drop' % (intf))

    def on_cascade_upstream_up(self, api_client, data):
        self.routesDict[api_client.get_peer_ip()] = dict()
        self.on_cascade_upstream_router_add(api_client, data["router-list"])

    def on_cascade_upstream_down(self, api_client):
        for router_id in api_client.get_router_info():
            self._removeRoutes(api_client.get_peer_ip(), router_id)
        del self.routesDict[api_client.get_peer_ip()]

    def on_cascade_upstream_router_add(self, api_client, data):
        self.on_cascade_upstream_router_lan_prefix_list_change(api_client, data)

    def on_cascade_upstream_router_remove(self, api_client, data):
        for router_id in data:
            self._removeRoutes(api_client.get_peer_ip(), router_id)

    def on_cascade_upstream_router_lan_prefix_list_change(self, api_client, data):
        for router_id in data:
            if "lan-prefix-list" not in data[router_id]:
                continue                # called by on_cascade_upstream_router_add()
            if router_id == api_client.get_peer_uuid():
                tlist = list(data[router_id]["lan-prefix-list"])
                for prefix in self.param.wanManager.vpnPlugin.get_prefix_list():
                    tlist.remove(prefix[0] + "/" + prefix[1])
            else:
                tlist = data[router_id]["lan-prefix-list"]
            self._updateRoutes(api_client.get_peer_ip(), router_id, tlist)

    def on_cascade_downstream_up(self, sproc, data):
        self.routesDict[sproc.get_peer_ip()] = dict()
        self.on_cascade_downstream_router_add(sproc, data["router-list"])

    def on_cascade_downstream_down(self, sproc):
        for router_id in sproc.get_router_info():
            self._removeRoutes(sproc.get_peer_ip(), router_id)
        del self.routesDict[sproc.get_peer_ip()]

    def on_cascade_downstream_router_add(self, sproc, data):
        self.on_cascade_downstream_router_lan_prefix_list_change(sproc, data)

    def on_cascade_downstream_router_remove(self, sproc, data):
        for router_id in data:
            self._removeRoutes(sproc.get_peer_ip(), router_id)

    def on_cascade_downstream_router_lan_prefix_list_change(self, sproc, data):
        for router_id in data:
            if "lan-prefix-list" in data[router_id]:
                self._updateRoutes(sproc.get_peer_ip(), router_id, data[router_id]["lan-prefix-list"])

    def _dispose(self):
        for p in self.pluginList:
            p.stop()
            logging.info("Traffic plugin \"%s\" deactivated." % (p.full_name))
        self.pluginList = []

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

    def _updateRoutes(self, gateway_ip, router_id, prefix_list):
        if router_id not in self.routesDict[gateway_ip]:
            self.routesDict[gateway_ip][router_id] = []
        with pyroute2.IPRoute() as ipp:
            # remove routes
            tlist = list(self.routesDict[gateway_ip][router_id])
            for prefix in tlist:
                if prefix not in prefix_list:
                    ipp.route("del", dst=self.__prefixConvert(prefix))
                    self.routesDict[gateway_ip][router_id].remove(prefix)
            # add routes
            for prefix in prefix_list:
                if prefix not in self.routesDict[gateway_ip][router_id]:
                    ipp.route("add", dst=self.__prefixConvert(prefix), gateway=gateway_ip)
                    self.routesDict[gateway_ip][router_id].append(prefix)

    def _removeRoutes(self, gateway_ip, router_id):
        if router_id in self.routesDict[gateway_ip]:
            with pyroute2.IPRoute() as ipp:
                for prefix in self.routesDict[gateway_ip][router_id]:
                    ipp.route("del", dst=self.__prefixConvert(prefix))
                del self.routesDict[gateway_ip][router_id]

    def __prefixConvert(self, prefix):
        tl = prefix.split("/")
        return tl[0] + "/" + str(WrtUtil.ipMaskToLen(tl[1]))


class _TrafficFacilityGroup:

    def __init__(self):
        self.priority = None
        self.facility_list = []
