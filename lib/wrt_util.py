#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import sys
import json
import socket
import shutil
import time
import logging
import ctypes
import errno
import subprocess
import threading
import ipaddress
import queue
import urllib.request
from collections import OrderedDict
from gi.repository import GLib


class WrtUtil:

    @staticmethod
    def isIpPublic(ip):
        ip2 = urllib.request.urlopen("https://ipinfo.io/ip").read().decode("UTF-8").strip()
        return ip == ip2

    @staticmethod
    def prefixConflict(prefix1, prefix2):
        netobj1 = ipaddress.IPv4Network(prefix1[0] + "/" + prefix1[1])
        netobj2 = ipaddress.IPv4Network(prefix2[0] + "/" + prefix2[1])
        return netobj1.overlaps(netobj2)

    @staticmethod
    def idleInvoke(func, *args):
        def _idleCallback(func, *args):
            func(*args)
            return False
        return GLib.idle_add(_idleCallback, func, *args)

    @staticmethod
    def restartProgram():
        python = sys.executable
        os.execl(python, python, * sys.argv)

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
    def nftForceDeleteTable(table):
        rc, msg = WrtUtil.shell("/sbin/nft list table %s" % (table), "retcode+stdout")
        if rc == 0:
            WrtUtil.shell("/sbin/nft delete table %s" % (table))

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
        except BaseException:
            self.parentfd.close()
            self.parentfd = None
            raise

    def __exit__(self, *_):
        self._setns(self.parentfd.fileno(), 0)
        self.parentfd.close()
        self.parentfd = None


class IdleQueue:

    def __init__(self):
        self.queue = queue.Queue()
        self.consumer = None

    def add(self, idleCallback, *args):
        self.queue.put((idleCallback, args))
        if self.consumer is None:
            self.consumer = GLib.idle_add(self._consumeFunc)

    def clear(self):
        if self.consumer is not None:
            GLib.source_remove(self.consumer)
            self.consumer = None
        self.queue = queue.Queue()

    def _consumeFunc(self):
        # add() and clear() may be called in _consumeFunc()
        if not self.queue.empty():
            idleCallback, args = self.queue.get()
            self.queue.task_done()
            idleCallback(*args)
        if not self.queue.empty():
            return True
        self.consumer = None
        return False


class JsonApiServer:

    def __init__(self, clientProcessorClass, ipList, port):
        self.flagError = GLib.IO_PRI | GLib.IO_ERR | GLib.IO_HUP | GLib.IO_NVAL

        self.serverSockList = []
        self.clientProcessorClass = clientProcessorClass

        self.globalLock = threading.Lock()
        self.threadDict = dict()

        self.bValidClient = False
        self.clientIpSet = set()

        self.bOneClientPerIp = False

        self.clientInitCallback = None
        self.clientTerminateCallback = None

        self.commandDict = dict()
        self.notifyList = []

        try:
            for ip in ipList:
                serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                serverSock.bind((ip, port))
                serverSock.listen(5)
                serverSock.setblocking(0)
                serverSourceId = GLib.io_add_watch(serverSock, GLib.IO_IN | self.flagError, self._onServerAccept)
                self.serverSockList.append((serverSock, serverSourceId))
        except BaseException:
            for serverSock, serverSourceId in self.serverSockList:
                GLib.source_remove(serverSourceId)
                serverSock.close()
            self.serverSockList = []

    def setClientValidating(self, value):
        assert isinstance(value, bool)
        self.bValidClient = value

    def addValidClientIp(self, ip):
        self.clientIpSet.add(ip)

    def removeValidClientIp(self, ip):
        self.clientIpSet.remove(ip)

    def setOneClientPerIp(self, value):
        assert isinstance(value, bool)
        self.bOneClientPerIp = value

    def setClientInitCallback(self, func):
        assert self.clientInitCallback is None
        self.clientInitCallback = func

    def setClientTerminateCallback(self, func):
        assert self.clientTerminateCallback is None
        self.clientTerminateCallback = func

    def addCommand(self, command, func):
        assert command not in self.commandDict
        self.commandDict[command] = func

    def addNotify(self, notify):
        assert notify not in self.notifyList
        self.notifyList.append(notify)

    def dispose(self):
        for serverSock, serverSourceId in self.serverSockList:
            GLib.source_remove(serverSourceId)
            serverSock.close()

        with self.globalLock:
            for sock in self.threadDict.keys():
                self._stopClient(sock)
        while len(self.threadDict) > 0:
            time.sleep(1.0)

    def getClients(self):
        pass

    def _onServerAccept(self, source, cb_condition):
        assert not (cb_condition & self.flagError)

        # accept connection
        new_sock = None
        addr = None
        try:
            new_sock, addr = source.accept()
        except socket.error as e:
            logging.debug("JsonApiServer.onServerAccept: Failed, %s, %s", e.__class__, e)
            return True

        # check client ip address
        if self.bValidClient:
            if addr[0] not in self.clientIpSet:
                logging.debug("JsonApiServer.onServerAccept: Reject, invalid client IP address %s" % (addr[0]))
                return True

        # if only one client per ip address
        if self.bOneClientPerIp:
            sockList = []
            with self.globalLock:
                for sock in self.threadDict.keys():
                    if sock.getpeeraddr[0] == addr[0]:
                        sockList.append(sock)
            for sock in sockList:
                self._stopClient(sock)
            while len(sockList) > 0:
                time.sleep(1.0)
                sockList2 = []
                for sock in sockList:
                    if sock in self.threadDict:
                        sockList2.append(sock)
                sockList = sockList2

        # create threads
        with self.globalLock:
            sendLock = threading.Lock()
            tRecv = _CommandThread(self, new_sock, addr[0], sendLock)
            tSend = _NotifyThread(self, new_sock, addr[0], sendLock)
            self.threadDict[new_sock] = (tRecv, tSend)
            tRecv.start()
            tSend.Start()

        # send init object
        if self.clientInitCallback is not None:
            data = self.clientInitCallback(new_sock.getpeeraddr())
            if data is not None:
                jsonObj = dict()
                jsonObj["init"] = data
                tSend.queue.put(jsonObj)

        return True

    def _stopClient(self, sock):
        tRecv, tSend = self.threadDict[sock]
        if tRecv is not None:
            tRecv.sock.shutdown(socket.SHUT_WR)
        if tSend is not None:
            tSend.bStop = True

    def _disposeClient(self, sock, elem_id):
        with self.globalLock:
            self.threadDict[sock][elem_id] = None
            if all(x is None for x in self.threadDict[sock]):
                if self.clientTerminateCallback is not None:
                    self.clientTerminateCallback(sock.getpeeraddr())
                del self.threadDict[sock]
                sock.close()


class JsonApiEndPoint:
    # sub-class must implement the following functions:
    #   on_error(self, e)
    #   on_command_XXX(self, data)
    #   on_notification_XXX(self, data)

    def __init__(self):
        self.iostream = None
        self.dis = None
        self.dos = None
        self.command_received = None
        self.command_sent = None

    def set_iostream_and_start(self, iostream):
        assert self.iostream is None

        self.iostream = iostream
        self.dis = Gio.DataInputStream.new(iostream.get_input_stream())
        self.dos = Gio.DataOutputStream.new(iostream.get_output_stream())
        self.dis.read_line_async(0, None, self._on_receive)     # fixme: 0 should be PRIORITY_DEFAULT, but I can't find it

    def close(self):
        if self.iostream is not None:
            self.iostream.close()

    def send_notification(self, notification, data):
        assert self.command_sent is None

        jsonObj = dict()
        jsonObj["notification"] = notification
        if data is not None:
            jsonObj["data"] = data
        self.dos.put_string(json.dumps(jsonObj) + "\n")

    def exec_command(self, command, data, return_callback=None, error_callback=None):
        assert self.command_sent is None

        jsonObj = dict()
        jsonObj["command"] = command
        if data is not None:
            jsonObj["data"] = data
        self.dos.put_string(json.dumps(jsonObj) + "\n")
        self.command_sent = (return_callback, error_callback)

    def _on_receive(self, source_object, res):
        class Excp1(Exception):
            pass

        line, len = source_object.read_line_finish_utf8(res)
        jsonObj = json.loads(line)
        try:
            if "command" in jsonObj:
                if self.command_received is not None:
                    raise Excp1("unexpected \"command\" message")
                funcname = "on_command_" + jsonObj["command"].replace("-", "_")
                if not hasattr(self, funcname):
                    raise Excp1("no callback for command " + jsonObj["command"])
                getattr(self, funcname)(jsonObj.get("data", None), self._send_return, self._send_error)                
                self.command_received = jsonObj["command"]
                return

            if "notification" in jsonObj:
                funcname = "on_notification_" + jsonObj["notification"].replace("-", "_")
                if not hasattr(self, funcname):
                    raise Excp1("no callback for notification " + jsonObj["notification"])
                getattr(self, funcname)(jsonObj.get("data", None))
                return

            if "return" in jsonObj:
                if self.command_sent is None:
                    raise Excp1("unexpected \"return\" message")
                cmd, return_cb, error_cb = self.command_sent
                if jsonObj["return"] is not None and return_cb is None:
                    raise Excp1("no return callback specified for command " + cmd)
                if return_cb is not None:
                    return_cb(jsonObj["return"])
                self.command_sent = None
                return
            elif "error" in jsonObj:
                if self.command_sent is None:
                    raise Excp1("unexpected \"error\" message")
                cmd, return_cb, error_cb = self.command_sent
                if error_cb is None:
                    raise Excp1("no error callback specified for command " + cmd)
                error_cb(jsonObj["error"])
                self.command_sent = None
                return
            else:
                raise Excp1("invalid message")
        except Excp1 as e:
            self.on_error(e)
            self.close()
        finally:
            self.dis.read_line_async(0, None, self._on_receive)

    def _send_return(self, data):
        assert self.command_received is not None

        jsonObj = dict()
        jsonObj["return"] = data
        self.dos.put_string(json.dumps(jsonObj) + "\n")
        self.command_received = None

    def _send_error(self, data):
        assert self.command_received is not None

        jsonObj = dict()
        jsonObj["error"] = data
        self.dos.put_string(json.dumps(jsonObj) + "\n")
        self.command_received = None


class JsonApiClient(JsonApiEndPoint):

    def __init__(self):
        super().__init__()
        self.ip = None
        self.port = None

    def connect(self, ip, port):
        assert self.ip is None and self.port is None

        self.ip = ip
        self.port = port

        sc = Gio.SocketClient.new()
        sc.set_family(Gio.SocketFamily.IPV4)
        sc.set_protocol(Gio.SocketProtocol.TCP)
        sc.connect_to_host_async(self.ip, self.port, None, self._on_connect)

    def close(self)
        super().close()

    def _on_connect(self, source_object, res):
        try:
            conn = source_object.connect_to_host_async_finish(res)
            self.set_iostream_and_start(conn)
            self.on_connected()
        except GLib.Error as e:
            self.on_error(e)


class JsonApiServer:

    def __init__(self, ipList, port):