#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import sys
import socket
import shutil
import struct
import fcntl
import ipaddress
import logging
import ctypes
import errno
import subprocess


class WrtUtil:

    @staticmethod
    def setInterfaceUpDown(ifname, upOrDown):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            ifreq = struct.pack("16sh", ifname.encode("ascii"), 0)
            ret = fcntl.ioctl(s.fileno(), 0x8913, ifreq)
            flags = struct.unpack("16sh", ret)[1]                   # SIOCGIFFLAGS

            if upOrDown:
                flags |= 0x1
            else:
                flags &= ~0x1

            ifreq = struct.pack("16sh", ifname.encode("ascii"), flags)
            fcntl.ioctl(s.fileno(), 0x8914, ifreq)                  # SIOCSIFFLAGS
        finally:
            s.close()

    @staticmethod
    def addBridge(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            fcntl.ioctl(s.fileno(), 0x89a0, ifname)                 # SIOCBRADDBR
        finally:
            s.close()

    @staticmethod
    def removeBridge(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            fcntl.ioctl(s.fileno(), 0x89a1, ifname)                 # SIOCBRDELBR
        finally:
            s.close()

    @staticmethod
    def addInterfaceToBridge(brname, ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            ifreq = struct.pack("16si", ifname.encode("ascii"), 0)
            ret = fcntl.ioctl(s.fileno(), 0x8933, ifreq)            # SIOCGIFINDEX
            ifindex = struct.unpack("16si", ret)[1]

            ifreq = struct.pack("16si", brname.encode("ascii"), ifindex)
            fcntl.ioctl(s.fileno(), 0x89a2, ifreq)                  # SIOCBRADDIF
        finally:
            s.close()

    @staticmethod
    def readDnsmasqHostFile(filename):
        """dnsmasq host file has the following format:
            1.1.1.1 myname
            ^       ^
            IP      hostname

           This function returns [(ip,hostname), (ip,hostname)]
        """
        ret = []
        with open(filename, "r") as f:
            for line in f.read().split("\n"):
                if line.startswith("#") or line.strip() == "":
                    continue
                t = line.split(" ")
                ret.append((t[0], t[1]))
        return ret

    @staticmethod
    def writeDnsmasqHostFile(filename, itemList):
        with open(filename, "w") as f:
            for item in itemList:
                f.write(item[0] + " " + item[1] + "\n")

    @staticmethod
    def recvUntilEof(sock):
        buf = bytes()
        while True:
            buf2 = sock.recv(4096)
            if len(buf2) == 0:
                break
            buf += buf2
        return buf

    @staticmethod
    def recvLine(sock):
        buf = bytes()
        while True:
            buf2 = sock.recv(1)
            if len(buf2) == 0 or buf2 == b'\n':
                break
            buf += buf2
        return buf

    @staticmethod
    def getLoggingLevel(logLevel):
        if logLevel == "CRITICAL":
            return logging.CRITICAL
        elif logLevel == "ERROR":
            return logging.ERROR
        elif logLevel == "WARNING":
            return logging.WARNING
        elif logLevel == "INFO":
            return logging.INFO
        elif logLevel == "DEBUG":
            return logging.DEBUG
        else:
            assert False

    @staticmethod
    def forceDelete(filename):
        if os.path.islink(filename):
            os.remove(filename)
        elif os.path.isfile(filename):
            os.remove(filename)
        elif os.path.isdir(filename):
            shutil.rmtree(filename)

    @staticmethod
    def mkDirAndClear(dirname):
        WrtUtil.forceDelete(dirname)
        os.mkdir(dirname)

    @staticmethod
    def shell(cmd, flags=""):
        """Execute shell command"""

        assert cmd.startswith("/")

        # Execute shell command, throws exception when failed
        if flags == "":
            retcode = subprocess.Popen(cmd, shell=True, universal_newlines=True).wait()
            if retcode != 0:
                raise Exception("Executing shell command \"%s\" failed, return code %d" % (cmd, retcode))
            return

        # Execute shell command, throws exception when failed, returns stdout+stderr
        if flags == "stdout":
            proc = subprocess.Popen(cmd,
                                    shell=True, universal_newlines=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            out = proc.communicate()[0]
            if proc.returncode != 0:
                raise Exception("Executing shell command \"%s\" failed, return code %d, output %s" % (cmd, proc.returncode, out))
            return out

        # Execute shell command, returns (returncode,stdout+stderr)
        if flags == "retcode+stdout":
            proc = subprocess.Popen(cmd,
                                    shell=True, universal_newlines=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            out = proc.communicate()[0]
            return (proc.returncode, out)

        assert False

    @staticmethod
    def ensureDir(dirname):
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    @staticmethod
    def getGatewayInterface():
        ret = WrtUtil.shell("/bin/route -n4", "stdout")
        # syntax: DestIp GatewayIp DestMask ... OutIntf
        m = re.search("^(0\\.0\\.0\\.0)\\s+([0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+)\\s+(0\\.0\\.0\\.0)\\s+.*\\s+(\\S+)$", ret, re.M)
        if m is None:
            return None
        return m.group(4)

    @staticmethod
    def getGatewayNexthop():
        ret = WrtUtil.shell("/bin/route -n4", "stdout")
        # syntax: DestIp GatewayIp DestMask ... OutIntf
        m = re.search("^(0\\.0\\.0\\.0)\\s+([0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+)\\s+(0\\.0\\.0\\.0)\\s+.*\\s+(\\S+)$", ret, re.M)
        if m is None:
            return None
        return m.group(2)

    @staticmethod
    def ipMaskToLen(mask):
        """255.255.255.0 -> 24"""

        netmask = 0
        netmasks = mask.split('.')
        for i in range(0, len(netmasks)):
            netmask *= 256
            netmask += int(netmasks[i])
        return 32 - (netmask ^ 0xFFFFFFFF).bit_length()

    @staticmethod
    def nftAddRule(table, chain, rule):
        """WARN: rule argument must use **standard** format, or you are not able to find the handle number"""

        # add rule
        WrtUtil.shell('/sbin/nft add rule %s %s %s' % (table, chain, rule))

        # obtain and return rule handle number
        msg = WrtUtil.shell("/sbin/nft list table %s -a" % (table), "stdout")
        mlist = list(re.finditer("^\\s+%s # handle ([0-9]+)$" % (rule), msg, re.M))
        assert len(mlist) == 1
        return int(mlist[0].group(1))

    @staticmethod
    def nftDeleteRule(table, chain, ruleHandle):
        WrtUtil.shell('/sbin/nft delete rule %s %s handle %d' % (table, chain, ruleHandle))

    @staticmethod
    def getFreeSocketPort(portType):
        if portType == "tcp":
            stlist = [socket.SOCK_STREAM]
        elif portType == "udp":
            stlist = [socket.SOCK_DGRAM]
        elif portType == "tcp+udp":
            stlist = [socket.SOCK_STREAM, socket.SOCK_DGRAM]
        else:
            assert False

        for port in range(10000, 65536):
            bFound = True
            for sType in stlist:
                s = socket.socket(socket.AF_INET, sType)
                try:
                    s.bind((('', port)))
                except socket.error:
                    bFound = False
                finally:
                    s.close()
            if bFound:
                return port

        raise Exception("no valid port")

    def ip2ipar(ip):
        AF_INET = 2
        # AF_INET6 = 10
        el = ip.split(".")
        assert len(el) == 4
        return (AF_INET, [bytes([int(x)]) for x in el])

    @staticmethod
    def getReservedIpv4NetworkList():
        return [
            ipaddress.IPv4Network("0.0.0.0/8"),
            ipaddress.IPv4Network("10.0.0.0/8"),
            ipaddress.IPv4Network("100.64.0.0/10"),
            ipaddress.IPv4Network("127.0.0.0/8"),
            ipaddress.IPv4Network("169.254.0.0/16"),
            ipaddress.IPv4Network("172.16.0.0/12"),
            ipaddress.IPv4Network("192.0.0.0/24"),
            ipaddress.IPv4Network("192.0.2.0/24"),
            ipaddress.IPv4Network("192.88.99.0/24"),
            ipaddress.IPv4Network("192.168.0.0/16"),
            ipaddress.IPv4Network("198.18.0.0/15"),
            ipaddress.IPv4Network("198.51.100.0/24"),
            ipaddress.IPv4Network("203.0.113.0/24"),
            ipaddress.IPv4Network("224.0.0.0/4"),
            ipaddress.IPv4Network("240.0.0.0/4"),
            ipaddress.IPv4Network("255.255.255.255/32"),
        ]

    @staticmethod
    def substractIpv4Network(ipv4Network, ipv4NetworkList):
        netlist = [ipv4Network]
        for n in ipv4NetworkList:
            tlist = []
            for n2 in netlist:
                if not n2.overlaps(n):
                    tlist.append(n2)                                # no need to substract
                    continue
                try:
                    tlist += list(n2.address_exclude(n))            # successful to substract
                except:
                    pass                                            # substract to none
            netlist = tlist
        return netlist

    @staticmethod
    def readDnsmasqLeaseFile(filename):
        """dnsmasq leases file has the following format:
             1108086503   00:b0:d0:01:32:86 142.174.150.208 M61480    01:00:b0:d0:01:32:86
             ^            ^                 ^               ^         ^
             Expiry time  MAC address       IP address      hostname  Client-id

           This function returns [(mac,ip,hostname), (mac,ip,hostname)]
        """

        pattern = "[0-9]+ +([0-9a-f:]+) +([0-9\.]+) +(\\S+) +\\S+"
        ret = []
        with open(filename, "r") as f:
            for line in f.read().split("\n"):
                m = re.match(pattern, line)
                if m is None:
                    continue
                if m.group(3) == "*":
                    item = (m.group(1), m.group(2), "")
                else:
                    item = (m.group(1), m.group(2), m.group(3))
                ret.append(item)
        return ret


class StdoutRedirector:

    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()


class NewMountNamespace:

    _CLONE_NEWNS = 0x00020000               # <linux/sched.h>
    _MS_REC = 16384                         # <sys/mount.h>
    _MS_PRIVATE = 1 << 18                   # <sys/mount.h>
    _libc = None
    _mount = None
    _setns = None
    _unshare = None

    def __init__(self):
        if self._libc is None:
            self._libc = ctypes.CDLL('libc.so.6', use_errno=True)
            self._mount = self._libc.mount
            self._mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
            self._mount.restype = ctypes.c_int
            self._setns = self._libc.setns
            self._unshare = self._libc.unshare

        self.parentfd = None

    def __enter__(self):
        self.parentfd = open("/proc/%d/ns/mnt" % (os.getpid()), 'r')

        # copied from unshare.c of util-linux
        try:
            if self._unshare(self._CLONE_NEWNS) != 0:
                e = ctypes.get_errno()
                raise OSError(e, errno.errorcode[e])

            srcdir = ctypes.c_char_p("none".encode("utf_8"))
            target = ctypes.c_char_p("/".encode("utf_8"))
            if self._mount(srcdir, target, None, (self._MS_REC | self._MS_PRIVATE), None) != 0:
                e = ctypes.get_errno()
                raise OSError(e, errno.errorcode[e])
        except:
            self.parentfd.close()
            self.parentfd = None
            raise

    def __exit__(self, *_):
        self._setns(self.parentfd.fileno(), 0)
        self.parentfd.close()
        self.parentfd = None


class JsonApiServer:

    def __init__(self, ip, port):
        self.flagError = GLib.IO_PRI | GLib.IO_ERR | GLib.IO_HUP | GLib.IO_NVAL

        self.serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSock.bind((ip, port))
        self.serverSock.listen(5)
        self.serverSock.setblocking(0)
        self.serverSourceId = GLib.io_add_watch(self.serverSock, GLib.IO_IN | self.flagError, self._onServerAccept)

        self.globalLock = threading.Lock()
        self.threadDict = dict()

        self.commandDict = dict()
        self.notifyList = []

    def addCommand(self, command, func):
        assert command not in self.commandDict
        self.commandDict[command] = func

    def addNotify(self, notify):
        assert notify not in self.notifyList
        self.notifyList.append(notify)

    def dispose(self):
        GLib.source_remove(self.serverSourceId)
        self.serverSock.close()

        with self.globalLock:
            for tRecv, tSend in self.threadDict:
                if tRecv is not None:
                    tRecv.sock.shutdown(socket.SHUT_WR)
                if tSend is not None:
                    tSend.bStop = True
        while len(self.threadDict) > 0:
            time.sleep(1.0)

    def sendNotify(self, notify, data):
        assert notify in self.notifyList

        jsonObj = dict()
        jsonObj["notify"] = notify
        if data is not None:
            jsonObj["data"] = data

        with self.globalLock:
            for tRecv, tSend in self.threadDict:
                if tSend is not None:
                    tSend.queue.put(jsonObj)

    def _onServerAccept(self, source, cb_condition):
        assert not (cb_condition & self.flagError)

        try:
            new_sock, addr = source.accept()
            with self.globalLock:
                sendLock = threading.Lock()
                tRecv = _CommandThread(self, new_sock, addr[0], sendLock)
                tSend = _NotifyThread(self, new_sock, addr[0], sendLock)
                self.threadDict[new_sock] = (tRecv, tSend)
                tRecv.start()
                tSend.Start()
            return True
        except socket.error as e:
            logging.debug("JsonApiServer.onServerAccept: Failed, %s, %s", e.__class__, e)
            return True

    def _disposeClient(sock, elem_id):
        with self.globalLock:
            self.threadDict[sock][elem_id] = None
            if all(x is None for x in self.threadDict[sock]):
                del self.threadDict[sock]
                sock.close()


class _CommandThread(threading.Thread):

    def __init__(self, pObj, sock, addr, sendLock):
        threading.Thread.__init__(self)
        self.pObj = pObj
        self.sock = sock
        self.addr = addr
        self.sendLock = sendLock

    def run(self):
        try:
            while True:
                buf = WrtUtil.recvLine(self.sock).decode("utf-8")
                if len(buf) == 0:
                    break
                try:
                    jsonObj = json.loads(buf)
                    if "command" not in jsonObj:
                        raise Exception("invalid command")
                    if jsonObj["command"] not in self.pObj.commandDict:
                        raise Exception("command %s not supported" % (jsonObj["command"]))

                    if "data" in jsonObj:
                        self.pObj.commandDict[jsonObj["command"]]()
                    else:
                        self.pObj.commandDict[jsonObj["command"]](jsonObj["data"])
                    logging.info("Process API command \"%s\" from \"%s\"", jsonObj["command"], self.addr)
                except Exception as e:
                    logging.error("Failed to process API command from %s, %s", self.addr, e)
                    logging.debug("_CommandThread.run: Exception, %s, %s", e.__class__, e)
        finally:
            self.pObj._disposeClient(self.sock, 0)


class _NotifyThread(threading.Thread):

    def __init__(self, pObj, sock, addr, sendLock):
        threading.Thread.__init__(self)
        self.pObj = pObj
        self.sock = sock
        self.addr = addr
        self.sendLock = sendLock
        self.queue = queue.queue()
        self.bStop = False

    def run(self):
        try:
            while True:
                if self.bStop:
                    break
                try:
                    jsonObj = self.queue.get(timeout=10)
                except queue.Empty:
                    continue

                if self.bStop:
                    break
                try:
                    buf = json.dumps(jsonObj)
                    with self.sendLock:
                        self.sock.send(buf)
                    logging.info("Send notify \"%s\" to \"%s\"", jsonObj["notify"], self.addr)
                except Exception as e:
                    logging.error("Failed to send notify to %s, %s", self.addr, e)
                    logging.debug("_NotifyThread.run: Exception, %s, %s", e.__class__, e)
                finally:
                    self.queue.task_done()
        finally:
            self.pObj._disposeClient(self.sock, 1)


class JsonApiClient:

    def __init__(self, ip, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((ip, port))
            _RecvThread(self).start()
        except:
            sock.close()
            raise

        self.notifyCallbackDict = dict()
        self.queue = queue.queue()

    def execCommand(self, command, data=None, timeout=None):
        jsonObj = dict()
        jsonObj["command"] = command
        if data is not None:
            jsonObj["data"] = data

        buf = json.dumps(jsonObj)
        self.sock.send(buf)

        while True:
            try:
                jsonObj = self.queue.get(timeout=10)
            except queue.Empty:
                continue
            try:
                if "return" in jsonObj:
                    return jsonObj["return"]
                else:
                    raise Exception("fixme")
            finally:
                self.queue.task_done()

    def registerNotifyCallback(self, notify, callback):
        self.notifyCallback[notify] = callback

    def dispose(self):
        self.sock.close()


class _RecvThread(threading.Thread):

    def __init__(self, pObj):
        threading.Thread.__init__(self)
        self.pObj = pObj

    def run(self):
        while True:
            buf = WrtUtil.recvLine(self.pObj.sock).decode("utf-8")
            if len(buf) == 0:
                break
            try:
                jsonObj = json.loads(buf)
                if "notify" in jsonObj:
                    if jsonObj["notify"] not in self.pObj.notifyCallbackDict:
                        raise Exception("notify %s not supported" % (jsonObj["notify"]))
                    self.pObj.notifyCallbackDict[jsonObj["notify"]]()
                elif "return" in jsonObj:
                else:
                    raise Exception("invalid content")

                if "data" in jsonObj:
                    self.pObj.commandDict[jsonObj["command"]]()
                else:
                    self.pObj.commandDict[jsonObj["command"]](jsonObj["data"])
                logging.info("Process API command \"%s\" from \"%s\"", jsonObj["command"], self.addr)
            except Exception as e:
                logging.error("Failed to process API command from %s, %s", self.addr, e)
                logging.debug("_CommandThread.run: Exception, %s, %s", e.__class__, e)