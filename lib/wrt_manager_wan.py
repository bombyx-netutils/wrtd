#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import json
import logging
import ipaddress
from collections import OrderedDict
from gi.repository import GLib
from gi.repository import GObject
from wrt_util import WrtUtil
from wrt_common import WrtCommon
from wrt_api_cascade import WrtCascadeApiClient


class WrtWanManager:

    # currently:
    # 1. default route is created by plugin
    # 2. self.param.ownResolvConf is created by plugin
    # these are to be modified

    # sub-host change should be dispatched in 10 seconds
    # vpn restart interval is 60 seconds

    def __init__(self, param):
        self.param = param
        self.wanConnPlugin = None

        self.vpnPlugin = None
        self.apiClient = None
        self.upstreamDict = None                # ordereddict<upstream-id, data>
        self.subHostDict = None                 # dict<upstream-ip, subhost-ip>
        self.vpnRestartCountDown = None

        logging.info("WAN: Start.")
        try:
            cfgfile = os.path.join(self.param.etcDir, "wan-connection.json")
            if os.path.exists(cfgfile):
                cfgObj = None
                with open(cfgfile, "r") as f:
                    cfgObj = json.load(f)
                self.wanConnPlugin = WrtCommon.getWanConnectionPlugin(self.param, cfgObj["plugin"])
                tdir = os.path.join(self.param.tmpDir, "wconn-%s" % (cfgObj["plugin"]))
                os.mkdir(tdir)
                self.wanConnPlugin.init2(cfgObj, tdir, self.param.ownResolvConf)
                self.wanConnPlugin.start()
                logging.info("WAN: Internet connection activated, plugin: %s." % (cfgObj["plugin"]))

                self._addNftRuleWan()
                logging.info("WAN: Firewall is up.")

                with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                    f.write("1")
                logging.info("WAN: IP forwarding enabled.")
            else:
                logging.info("WAN: No internet connection configured.")

            cfgfile = os.path.join(self.param.etcDir, "wan-vpn.json")
            if os.path.exists(cfgfile):
                cfgObj = None
                with open(cfgfile, "r") as f:
                    cfgObj = json.load(f)
                self.vpnPlugin = WrtCommon.getWanVpnPlugin(self.param, cfgObj["plugin"])
                tdir = os.path.join(self.param.tmpDir, "wvpn-%s" % (cfgObj["plugin"]))
                os.mkdir(tdir)
                self.vpnPlugin.init2(cfgObj, self.vpnPlugin.get_interface(), tdir)
                self.vpnTimer = GObject.timeout_add_seconds(10, self._vpnTimerCallback)
                self.vpnRestartCountDown = 0
                logging.info("WAN: VPN activated, plugin: %s." % (cfgObj["plugin"]))
            else:
                logging.info("WAN: No VPN configured.")
        except:
            self.dispose()
            raise

    def dispose(self):
        if self.vpnPlugin is not None:
            GLib.source_remove(self.vpnTimer)
            self.vpnPlugin.stop()
            self.vpnPlugin = None
            logging.info("WAN: VPN deactivated.")
        if self.wanConnPlugin is not None:
            with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                f.write("0")
            self.wanConnPlugin.stop()
            self.wanConnPlugin = None
            logging.info("WAN: Internet connection deactivated.")
        logging.info("WAN: Terminated.")

    def on_host_appear(self, ipDataDict):
        if self.vpnPlugin is None:
            return
        if self.apiClient is None:
            return

        ipDataDict2 = dict()
        for ip, data in ipDataDict.items():
            empty = None
            for k, v in self.subHostDict.items():
                if v is None and empty is None:
                    empty = k
                    break
            WrtUtil.shell("/bin/ifconfig %s add %s" % (self.vpnPlugin.get_interface(), empty))
            self._addNftRuleVpnSubHost(ip, empty)
            self.subHostDict[empty] = ip
            ipDataDict2[empty] = data
        self.apiClient.addSubhost(ipDataDict2)

    def on_host_disappear(self, ipList):
        if self.vpnPlugin is None:
            return
        if self.apiClient is None:
            return

        ipList2 = []
        for ip in ipList:
            for k, v in self.subHostDict.items():
                if v == ip:
                    self.subHostDict[k] = None
                    self._removeNftRuleSubHost(v, k)
                    WrtUtil.shell("/bin/ifconfig %s del %s" % (self.vpnPlugin.get_interface(), k))
                    ipList2.append(k)
                    break
        self.apiClient.removeSubhost(ipList2)

    def _addNftRuleWan(self):
        intf = self.wanConnPlugin.get_out_interface()
        WrtUtil.shell('/sbin/nft add rule wrtd natpost oifname %s masquerade' % (intf))
        WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s ct state established,related accept' % (intf))
        WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s ip protocol icmp accept' % (intf))
        WrtUtil.shell('/sbin/nft add rule wrtd fw iifname %s drop' % (intf))

    def _addNftRuleVpnSubHost(self, subHostIp, natIp):
        WrtUtil.shell('/sbin/nft add rule wrtd natpre ip daddr %s iif %s dnat %s' % (natIp, self.vpnPlugin.get_interface(), subHostIp))
        WrtUtil.shell('/sbin/nft add rule wrtd natpost ip saddr %s oif %s snat %s' % (subHostIp, self.vpnPlugin.get_interface(), natIp))

    def _removeNftRuleSubHost(self, subHostIp, natIp):
        rc, msg = WrtUtil.shell('/sbin/nft list table ip wrtd -a', "retcode+stdout")
        if rc != 0:
            return
        m = re.search("\\s*ip daddr %s iif \"%s\" dnat to %s # handle ([0-9]+)" % (natIp, self.vpnPlugin.get_interface(), subHostIp), msg, re.M)
        if m is not None:
            WrtUtil.shell("/sbin/nft delete rule wrtd natpre handle %s" % (m.group(1)))
        m = re.search("\\s*ip saddr %s oif \"%s\" snat to %s # handle ([0-9]+)" % (subHostIp, self.vpnPlugin.get_interface(), natIp), msg, re.M)
        if m is not None:
            WrtUtil.shell("/sbin/nft delete rule wrtd natpost handle %s" % (m.group(1)))

    def _vpnTimerCallback(self):
        if self.vpnRestartCountDown is None:
            if self.vpnPlugin.is_alive():
                return True
            else:
                # vpn is in bad state, stop it now, restart it in the next cycle
                self._stopVpn()
                self.vpnRestartCountDown = 6
                logging.info("VPN disconnected.")
                return True

        if self.vpnRestartCountDown > 0:
            self.vpnRestartCountDown -= 1
            return True

        logging.info("Establishing VPN connection.")
        try:
            self.vpnPlugin.start()

            self.apiClient = WrtCascadeApiClient(self.vpnPlugin.get_remote_ip(), self.param.cascadeApiPort)
            initData = self.apiClient.connect()

            self.upstreamDict = OrderedDict()
            for k, v in initData["upstream"]:
                self.upstreamDict[k] = _UpStreamInfo(v)

            self.subHostDict = dict()
            if True:
                ip = initData["subhost-start"]
                while ip != initData["subhost-end"]:
                    self.subHostDict[ip] = None
                    ip = str(ipaddress.IPv4Address(ip) + 1)
                self.subHostDict[ip] = None

            logging.info("VPN connected.")
        except Exception as e:
            self._stopVpn()
            self.vpnRestartCountDown = 6
            logging.error("Failed to establish VPN connection, %s", e)
            return True

        # check upstream uuid and restart if neccessary
        if self._checkAndChangeUpstreamUuid():
            logging.error("Router UUID duplicated with upstream.")
            os.kill(os.getpid(), signal.SIGHUP)
            return True
        
        # check upstream prefix and restart if neccessary
        if self._checkAndChangeUpstreamPrefix():
            logging.error("Bridge prefix duplicated with upstream.")
            os.kill(os.getpid(), signal.SIGHUP)
            return True

        return True

    def _stopVpn(self):
        self.vpnRestartCountDown = None
        self.subHostDict = None
        if self.apiClient is not None:
            self.apiClient.dispose()
            self.apiClient = None
        self.vpnPlugin.stop()
        self.vpnPlugin = None

    def _checkAndChangeUpstreamUuid(self):
        if self.param.uuid not in self.upstreamDict.keys():
            return False

        # we don't change uuid actually, duplicated uuid is impossible
        return True

    def _checkAndChangeUpstreamPrefix(self):
        pendingBridges = []
        for bridge in self.param.lanManager.get_bridges():
            pIp, pMask = bridget.get_prefix()
            for uinfo in self.upstreamDict:
                c = len(pendingBridges)
                for prefix in uinfo.prefixList:
                    if ipaddress.IPv4Network(pIp + "/" + pMask).overlaps(ipaddress.IPv4Network(prefix)):
                        pendingBridges.append(bridge)
                        break
                if len(pendingBridges) > c:
                    break
        if pendingBridges == []:
            return False

        for bridge in pendingBridges:
            pIpNew = None
            pMaskNew = None
            for i in range(0, 256):
                new_pip = "192.168.%d.0" % (i)
                new_mask = "255.255.255.0"
                overlap = False
                for uinfo in self.upstreamDict:
                    for prefix in uinfo.prefixList:
                        if ipaddress.IPv4Network(new_pip + "/" + new_mask).overlaps(ipaddress.IPv4Network(prefix)):
                            overlap = True
                if not overlap:
                    pIpNew = new_pip
                    pMaskNew = new_mask
                    break
            #fixme



class _UpStreamInfo:

    def __init__(self, jsonObj):
        self.prefixList = jsonObj["prefix-list"]