#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import glob
import fcntl
from wrt_util import WrtUtil


class WrtCommon:

    @staticmethod
    def cleanupEtcHosts():
        bNoOp = True
        lineList = []
        lineList2 = []
        with open("/etc/hosts", "r") as f:
            b = -1
            for line in f.read().split("\n"):
                if line == "### fpemud-wrt begin ###":
                    b = 0
                    bNoOp = False
                if b == -1:
                    lineList.append(line)
                if b == 1:
                    lineList2.append(line)
                if line == "### fpemud-wrt end ###":
                    b = 1
                    bNoOp = False
        if bNoOp:
            return

        lineList += lineList2
        while len(lineList) > 0 and lineList[-1] == "":
            del lineList[-1]

        with open("/etc/hosts", "w") as f:
            f.write("\n".join(lineList))
            f.write("\n")

    @staticmethod
    def syncToEtcHosts(tmpDir):
        lineList = []
        lineList2 = []
        with open("/etc/hosts", "r") as f:
            b = -1
            for line in f.read().rstrip("\n").split("\n"):
                if line == "### fpemud-wrt begin ###":
                    b = 0
                if b == -1:
                    lineList.append(line)
                if b == 1:
                    lineList2.append(line)
                if line == "### fpemud-wrt end ###":
                    b = 1

        lineList.append("### fpemud-wrt begin ###")
        for fn in glob.glob(os.path.join(tmpDir, "hosts.d", "*")):
            for ip, hostname in WrtUtil.readDnsmasqHostFile(fn):
                lineList.append("%s %s" % (ip, hostname))
        for r in WrtUtil.readDnsmasqLeaseFile(os.path.join(tmpDir, "dnsmasq.leases")):
            if r[2] == "":
                continue
            lineList.append("%s %s" % (r[1], r[2]))
        lineList.append("### fpemud-wrt end ###")

        lineList += lineList2
        while len(lineList) > 0 and lineList[-1] == "":
            del lineList[-1]

        with open("/etc/hosts", "w") as f:
            f.write("\n".join(lineList))
            f.write("\n")


class DnsMasqHostFilesLock:

    def __init__(self, tmpDir):
        self.lockFile = os.path.join(tmpDir, "hosts.d", ".lock")
        self.lockFd = None

    def __enter__(self):
        try:
            self.lockFd = os.open(self.lockFile, os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC, 0o600)
            fcntl.lockf(self.lockFd, fcntl.LOCK_EX)
        except:
            if self.lockFd is not None:
                os.close(self.lockFd)
                self.lockFd = None

    def __exit__(self, *_):
        os.close(self.lockFd)
        self.lockFd = None
