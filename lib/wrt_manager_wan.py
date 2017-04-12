#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import json
import time
import signal
import socket
import logging
import threading
from gi.repository import GLib
from gi.repository import GObject
from wrt_util import WrtUtil
from wrt_common import WrtCommon


class WrtWanManager:

    # currently:
    # 1. default route is created by plugin
    # 2. /etc/resolv.conf is created by plugin
    # these are to be modified

    # sub-host change should be dispatched in 10 seconds
    # vpn restart interval is 60 seconds

    def __init__(self, param):
        self.param = param

        logging.info("WAN: Start.")
        try:
            cfgfile = os.path.join(self.param.etcDir, "wan-connection.json")
            if os.path.exists(cfgfile):
                cfgObj = None
                with open(cfgfile, "r") as f:
                    cfgObj = json.load(f)
                self.wanConnPlugin = WrtCommon.getWanConnectionPlugin(cfgObj["plugin"])
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
                self.vpnPlugin = WrtCommon.getVpnPlugin(cfgObj["plugin"])
                tdir = os.path.join(self.param.tmpDir, "wvpn-%s" % (cfgObj["plugin"]))
                os.mkdir(tdir)
                self.vpnPlugin.init2(cfgObj, self.param.vpnIntf, tdir)
                self.vpnTimer = GObject.timeout_add_seconds(10, self._vpnTimerCallback)
                self.vpnRestartCountDown = 0
                logging.info("WAN: VPN activated, plugin: %s." % (cfgObj["plugin"]))
            else:
                logging.info("WAN: No VPN configured.")
        except:
            self.dispose()
            raise

    def dispose(self):
        if hasattr(self, "vpnPlugin"):
            GLib.source_remove(self.vpnTimer)
            self.vpnPlugin.stop()
            del self.vpnRestartCountDown
            del self.vpnTimer
            del self.vpnPlugin
            logging.info("WAN: VPN deactivated.")
        if hasattr(self, "wanConnPlugin"):
            with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
                f.write("0")
            self.wanConnPlugin.stop()
            del self.wanConnPlugin
            WrtUtil.forceDelete("/etc/resolv.conf")
            WrtUtil.setInterfaceUpDown(self.wanConnPlugin.getOutInterface(), False)
            logging.info("WAN: Internet connection deactivated.")
        logging.info("WAN: Terminated.")

    def _addNftRuleWan(self):
        intf = self.wanConnPlugin.getOutInterface()
        WrtUtil.shell('/sbin/nft add rule wrtd natpost oif %s masquerade' % (intf))
        WrtUtil.shell('/sbin/nft add rule wrtd fw iif %s ct state established,related accept' % (intf))
        WrtUtil.shell('/sbin/nft add rule wrtd fw iif %s ip protocol icmp accept' % (intf))
        WrtUtil.shell('/sbin/nft add rule wrtd fw iif %s drop' % (intf))

    def _addNftRuleVpnSubHost(self, subHostIp, natIp):
        WrtUtil.shell('/sbin/nft add rule wrtd natpre ip daddr %s iif %s dnat %s' % (natIp, self.param.vpnIntf, subHostIp))
        WrtUtil.shell('/sbin/nft add rule wrtd natpost ip saddr %s oif %s snat %s' % (subHostIp, self.param.vpnIntf, natIp))

    def _removeNftRuleSubHost(self, subHostIp, natIp):
        rc, msg = WrtUtil.shell('/sbin/nft list table ip wrtd -a', "retcode+stdout")
        if rc != 0:
            return
        m = re.search("\\s*ip daddr %s iif \"%s\" dnat to %s # handle ([0-9]+)" % (natIp, self.param.vpnIntf, subHostIp), msg, re.M)
        if m is not None:
            WrtUtil.shell("/sbin/nft delete rule wrtd natpre handle %s" % (m.group(1)))
        m = re.search("\\s*ip saddr %s oif \"%s\" snat to %s # handle ([0-9]+)" % (subHostIp, self.param.vpnIntf, natIp), msg, re.M)
        if m is not None:
            WrtUtil.shell("/sbin/nft delete rule wrtd natpost handle %s" % (m.group(1)))

    def _vpnTimerCallback(self):
        if self.vpnRestartCountDown is None:
            if self.vpnPlugin.is_alive():
                # vpn is in good state
                try:
                    self._setSubHosts()
                except Exception as e:
                    self._stopVpn()
                    self.vpnRestartCountDown = 6
                    logging.error("VPN disconnected, %s", e)
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

        self.subHostListener = None
        self.subHostDict = dict()
        try:
            self.vpnPlugin.start()

            # create listener and register sub-host owner
            self.subHostListener = _SubHostListener(self, self.vpnPlugin.get_local_ip(), self.vpnPlugin.get_remote_ip())
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect((self.vpnPlugin.get_remote_ip(), self.param.vpnApiPort))
                sock.send(("register-subhosts-owner %d" % (self.subHostListener.port)).encode("utf-8"))
                sock.shutdown(socket.SHUT_WR)
                buf = WrtUtil.recvUntilEof(sock).decode("utf-8")
                jsonObj = json.loads(buf)
                if jsonObj["result"] == "error":
                    raise Exception(jsonObj["error"])
                for i in range(0, jsonObj["count"]):
                    t = self.vpnPlugin.get_remote_ip().split(".")
                    t[3] = str(jsonObj["start"] + i)
                    self.subHostDict[".".join(t)] = None
            finally:
                sock.close()

            # update sub-hosts
            self._setSubHosts()

            self.vpnRestartCountDown = None
            logging.info("VPN connected.")
        except Exception as e:
            self._stopVpn()
            self.vpnRestartCountDown = 6
            logging.error("Failed to establish VPN connection, %s", e)

        return True

    def _stopVpn(self):
        if hasattr(self, "subHostDict"):
            del self.subHostDict
        if hasattr(self, "subHostListener"):
            if self.subHostListener is not None:
                self.subHostListener.dispose()
            del self.subHostListener
        self.vpnPlugin.stop()

    def _setSubHosts(self):
        clientList = []
        if True:
            class _Tmp:
                pass
            leaseFile = os.path.join(self.param.tmpDir, "dnsmasq.leases")
            for mac, ip, hostname in WrtUtil.readDnsmasqLeaseFile(leaseFile):
                client = _Tmp()
                client.mac = mac
                client.ip = ip
                client.hostname = hostname
                clientList.append(client)
        changed = False

        # check for remove/change
        for k, v in self.subHostDict.items():
            if v is None:
                continue
            if not any(x.ip == v[0] and x.hostname == v[1] for x in clientList):
                print("debugr", self.subHostDict, k, v[0])
                self._removeNftRuleSubHost(v[0], k)
                WrtUtil.shell("/bin/ifconfig %s del %s" % (self.param.vpnIntf, k))
                self.subHostDict[k] = None
                changed = True

        # check for addtion
        for client in clientList:
            found = False
            empty = None
            for k, v in self.subHostDict.items():
                if v is None:
                    if empty is None:
                        empty = k
                else:
                    if client.ip == v[0] and client.hostname == v[1]:
                        found = True
                        break
            if not found and empty is not None:
                print("debug", self.subHostDict, empty, client.ip, client.hostname)
                WrtUtil.shell("/bin/ifconfig %s add %s" % (self.param.vpnIntf, empty))
                self._addNftRuleVpnSubHost(client.ip, empty)
                self.subHostDict[empty] = (client.ip, client.hostname)
                changed = True

        # no change
        if not changed:
            return

        # convert to json object
        jsonObj = []
        for k, v in self.subHostDict.items():
            if v is None:
                continue
            if v[1] == "":
                continue        # not giving hostname to us, ignore it
            jsonObj.append({
                "ip": k,
                "hostname": v[1],
            })

        # update sub-hosts
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((self.vpnPlugin.get_remote_ip(), self.param.vpnApiPort))
            sock.send(("update-subhosts %s" % (json.dumps(jsonObj))).encode("utf-8"))
            sock.shutdown(socket.SHUT_WR)
            buf = WrtUtil.recvUntilEof(sock).decode("utf-8")
            jsonObj = json.loads(buf)
            if jsonObj["result"] == "error":
                raise Exception(jsonObj["error"])
            logging.info("Sub-hosts updated.")
            logging.debug("Sub-hosts update: %s", json.dumps(jsonObj))
        finally:
            sock.close()


class _SubHostListener:

    def __init__(self, pObj, localIp, remoteIp):
        self.param = pObj.param
        self.pObj = pObj
        self.port = WrtUtil.getFreeSocketPort("tcp")

        self.serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSock.bind((localIp, self.port))
        self.serverSock.listen(5)
        self.serverSock.setblocking(0)
        self.serverSourceId = GLib.io_add_watch(self.serverSock, GLib.IO_IN | _flagError, self._onServerAccept)

        self.threadSet = set()
        self.threadSetLock = threading.Lock()

        self.remoteIp = remoteIp

    def dispose(self):
        GLib.source_remove(self.serverSourceId)
        self.serverSock.close()
        while len(self.threadSet) > 0:
            time.sleep(1.0)

    def _onServerAccept(self, source, cb_condition):
        assert not (cb_condition & _flagError)

        try:
            new_sock, addr = source.accept()
            with self.threadSetLock:
                th = _SubHostProcessThread(self, new_sock)
                self.threadSet.add(th)
                th.start()
            return True
        except socket.error as e:
            logging.debug("_SubHostListener._onServerAccept: Failed, %s, %s", e.__class__, e)
            return True


class _SubHostProcessThread(threading.Thread):

    def __init__(self, pObj, sock):
        threading.Thread.__init__(self)
        self.param = pObj.param
        self.pObj = pObj
        self.sock = sock

    def run(self):
        fname = os.path.join(self.param.tmpDir, "hosts.d", "hosts.vpn")
        try:
            buf = WrtUtil.recvUntilEof(self.sock).decode("utf-8")
            itemList = self._jsonObj2ItemList(json.loads(buf))
            WrtUtil.writeDnsmasqHostFile(fname, itemList)
            self._dnsmasqReloadHosts()                          # bad design. dnsmasq belongs to LanManager. we should notify the LanManager to do dnsmasq reloading
            WrtCommon.syncToEtcHosts(self.param.tmpDir)
        finally:
            with self.pObj.threadSetLock:
                self.pObj.threadSet.remove(self)
            self.sock.close()

    def _dnsmasqReloadHosts(self):
        with open(os.path.join(self.param.tmpDir, "dnsmasq.pid"), "r") as f:
            pid = int(f.read().rstrip("\n"))
            os.kill(pid, signal.SIGHUP)

    def _jsonObj2ItemList(self, jsonObj):
        itemList = []
        for host in jsonObj:
            itemList.append((host["ip"], host["hostname"]))
        return itemList


_flagError = GLib.IO_PRI | GLib.IO_ERR | GLib.IO_HUP | GLib.IO_NVAL
