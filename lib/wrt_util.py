#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import sys
import socket
import shutil
import logging
import ctypes
import errno
import threading
import subprocess
import ipaddress
import iptc
from collections import OrderedDict
from gi.repository import GLib


class WrtUtil:

    @staticmethod
    def is_int(s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    @staticmethod
    def ipMaskToPrefix(ip, netmask):
        netobj = ipaddress.IPv4Network(ip + "/" + netmask, strict=False)
        return (str(netobj.network_address), str(netobj.netmask))

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
    def dnsmasqHostFileToDict(filename):
        ret = dict()
        with open(filename, "r") as f:
            for line in f.read().split("\n"):
                if line.startswith("#") or line.strip() == "":
                    continue
                t = line.split(" ")
                ret[t[0]] = t[1]
        return ret

    @staticmethod
    def dnsmasqHostFileToOrderedDict(filename):
        ret = OrderedDict()
        with open(filename, "r") as f:
            for line in f.read().split("\n"):
                if line.startswith("#") or line.strip() == "":
                    continue
                t = line.split(" ")
                ret[t[0]] = t[1]
        return ret

    @staticmethod
    def dictToDnsmasqHostFile(ipHostnameDict, filename):
        with open(filename, "w") as f:
            for ip, hostname in ipHostnameDict.items():
                f.write(ip + " " + hostname + "\n")

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

           This function returns [(expiry-time,mac,ip,hostname,client-id), (expiry-time,mac,ip,hostname,client-id)]
        """

        pattern = "([0-9]+) +([0-9a-f:]+) +([0-9\.]+) +(\\S+) +(\\S+)"
        ret = []
        with open(filename, "r") as f:
            for line in f.read().split("\n"):
                m = re.match(pattern, line)
                if m is None:
                    continue
                expiryTime = m.group(1)
                mac = m.group(2)
                ip = m.group(3)
                hostname = "" if m.group(4) == "*" else m.group(4)
                clientId = "" if m.group(5) == "*" else m.group(5)
                ret.append((expiryTime, mac, ip, hostname, clientId))
        return ret

    @staticmethod
    def iptablesIsEmpty():
        for tname in iptc.Table.ALL:
            table = iptc.Table(tname)
            for chain in table.chains:
                if not table.builtin_chain(chain):
                    return False
                if chain.rules != []:
                    return False
        return True

    @staticmethod
    def iptablesSetEmpty():
        for tname in iptc.Table.ALL:
            table = iptc.Table(tname)
            table.flush()
            for chain in table.chains:
                chain.flush()
        return True


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


class UrlOpenAsync(threading.Thread):

    def __init__(self, url, ok_callback, error_callback):
        super().__init__()

        self.url = url
        self.ok_callback = ok_callback
        self.error_callback = error_callback
        self.proc = None
        self.idleId = None
        self.bComplete = False

    def start(self):
        self.proc = subprocess.Popen(["/usr/bin/curl", self.url],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        super().start()

    def cancel(self):
        assert self.proc is not None and not self.bComplete

        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait()
        self.join()
        GLib.source_remove(self.idleId)

    def run(self):
        out, err = self.proc.communicate()
        out = out.decode("utf-8").replace("\n", "")
        err = err.decode("utf-8")
        if self.proc.returncode == 0:
            self.idleId = GLib.idle_add(self._idleCallback, self.ok_callback, out)
        else:
            self.idleId = GLib.idle_add(self._idleCallback, self.error_callback, self.proc.returncode, err)

    def _idleCallback(self, func, *args):
        try:
            func(*args)
        except:
            logging.error("Error occured in UrlOpenAsync idle callback", exc_info=True)
        finally:
            self.bComplete = True
            return False
