#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import sys
import json
import socket
import shutil
import logging
import ctypes
import errno
import subprocess
import ipaddress
import urllib.request
from gi.repository import Gio
from gi.repository import GLib


class WrtUtil:

    @staticmethod
    def callFunc(obj, funcName, *args):
        if hasattr(obj, funcName):
            getattr(obj, funcName)(*args)

    @staticmethod
    def isIpPublic(ip):
        ip2 = urllib.request.urlopen("https://ipinfo.io/ip").read().decode("UTF-8").strip()
        return ip == ip2

    @staticmethod
    def prefixListConflict(prefixList1, prefixList2):
        for prefix1 in prefixList1:
            for prefix2 in prefixList2:
                netobj1 = ipaddress.IPv4Network(prefix1[0] + "/" + prefix1[1])
                netobj2 = ipaddress.IPv4Network(prefix2[0] + "/" + prefix2[1])
                if netobj1.overlaps(netobj2):
                    return True
        return False

    @staticmethod
    def prefixConflictWithPrefixList(prefix, prefixList):
        for prefix2 in prefixList:
            netobj1 = ipaddress.IPv4Network(prefix[0] + "/" + prefix[1])
            netobj2 = ipaddress.IPv4Network(prefix2[0] + "/" + prefix2[1])
            if netobj1.overlaps(netobj2):
                return True
        return False

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


class JsonApiEndPoint:
    # sub-class must implement the following functions:
    #   on_command_XXX_return(self, data)
    #   on_command_XXX_error(self, reason)
    #   on_notification_XXX(self, data)
    #   on_error(self, excp)
    #   on_close(self)
    #
    # exception in on_command_XXX_return(), on_command_XXX_error(), on_notification_XXX() would close the object and iostream
    # no exception is allowed in on_error(), on_close().
    # close(), send_notification(), exec_command() should not be called in on_XXX().
    # This class is not thread-safe.

    def __init__(self):
        self.iostream = None
        self.dis = None
        self.dos = None
        self.command_received = None
        self.command_sent = None

    def set_iostream_and_start(self, iostream):
        assert self.iostream is None

        try:
            self.iostream = iostream
            self.dis = Gio.DataInputStream.new(iostream.get_input_stream())
            self.dos = Gio.DataOutputStream.new(iostream.get_output_stream())
            self.dis.read_line_async(0, None, self._on_receive)     # fixme: 0 should be PRIORITY_DEFAULT, but I can't find it
        except BaseException:
            self.dis = None
            self.dos = None
            self.iostream = None

    def close(self):
        if self.iostream is not None:
            self.on_close()
            self.iostream.close()
        self.command_sent = None
        self.command_received = None
        self.dis = None
        self.dos = None
        self.iostream = None

    def send_notification(self, notification, data):
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
        self.command_sent = (command, return_callback, error_callback)

    def _on_receive(self, source_object, res):
        try:
            line, len = source_object.read_line_finish_utf8(res)
            if line is None:
                raise Exception("socket closed by peer")

            jsonObj = json.loads(line)
            while True:
                if "command" in jsonObj:
                    if self.command_received is not None:
                        raise Exception("unexpected \"command\" message")
                    funcname = "on_command_" + jsonObj["command"].replace("-", "_")
                    if not hasattr(self, funcname):
                        raise Exception("no callback for command " + jsonObj["command"])
                    self.command_received = jsonObj["command"]
                    getattr(self, funcname)(jsonObj.get("data", None), self._send_return, self._send_error)
                    break

                if "notification" in jsonObj:
                    funcname = "on_notification_" + jsonObj["notification"].replace("-", "_")
                    if not hasattr(self, funcname):
                        raise Exception("no callback for notification " + jsonObj["notification"])
                    getattr(self, funcname)(jsonObj.get("data", None))
                    break

                if "return" in jsonObj:
                    if self.command_sent is None:
                        raise Exception("unexpected \"return\" message")
                    cmd, return_cb, error_cb = self.command_sent
                    if jsonObj["return"] is not None and return_cb is None:
                        raise Exception("no return callback specified for command " + cmd)
                    if return_cb is not None:
                        return_cb(jsonObj["return"])
                    self.command_sent = None
                    break

                if "error" in jsonObj:
                    if self.command_sent is None:
                        raise Exception("unexpected \"error\" message")
                    cmd, return_cb, error_cb = self.command_sent
                    if error_cb is None:
                        raise Exception("no error callback specified for command " + cmd)
                    error_cb(jsonObj["error"])
                    self.command_sent = None
                    break

                raise Exception("invalid message")

            self.dis.read_line_async(0, None, self._on_receive)
        except Exception as e:
            self.on_error(e)
            self.close()

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
