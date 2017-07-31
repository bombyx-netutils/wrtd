#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import logging
import subprocess
from wrt_util import WrtUtil


class WrtTrafficManager:

    def __init__(self, param):
        self.param = param
        self.cfgFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.conf")
        self.pidFile = os.path.join(self.param.tmpDir, "l2-dnsmasq.pid")
        self.logger = logging.getLogger(self.__module__ + "." + self.__class__.__name__)

        self.wanServDict = dict()           # dict<name,json-object>
        self.tfacGroupDict = dict()         # dict<name,_TrafficFacilityGroup>

        self.dnsPort = None
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


class _TrafficFacilityGroup:

    def __init__(self):
        self.priority = None
        self.facility_list = []






        # # add nat rule
        # subprocess.check_call(["/sbin/nft", "add", "table", "ip", "cgfw"])
        # subprocess.check_call(["/sbin/nft", "add", "chain", "cgfw", "fw", "{", "type", "filter", "hook", "prerouting", "priority", "0", ";", "}"])
        # subprocess.check_call(["/sbin/nft", "add", "chain", "cgfw", "natpre", "{", "type", "nat", "hook", "prerouting", "priority", "0", ";", "}"])
        # subprocess.check_call(["/sbin/nft", "add", "chain", "cgfw", "natpost", "{", "type", "nat", "hook", "postrouting", "priority", "0", ";", "}"])
        # subprocess.check_call(["/sbin/nft", "add", "rule", "cgfw", "fw", "iifname", "\"cgfw\"", "ct", "state", "established,related", "accept"])
        # subprocess.check_call(["/sbin/nft", "add", "rule", "cgfw", "fw", "iifname", "\"cgfw\"", "ip", "protocol", "icmp", "accept"])
        # subprocess.check_call(["/sbin/nft", "add", "rule", "cgfw", "fw", "iifname", "\"cgfw\"", "drop"])
        # subprocess.check_call(["/sbin/nft", "add", "rule", "cgfw", "natpost", "oifname", "\"cgfw\"", "masquerade"])
