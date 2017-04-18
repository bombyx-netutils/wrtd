#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

class WrtTrafficCop:

    def __init__(self, param):
        self.param = param
        self.cfgFile = os.path.join(self.tmpDir, "l2-dnsmasq.conf")
        self.pidFile = os.path.join(self.tmpDir, "l2-dnsmasq.pid")

        self.dnsPort = None
        self.dnsmasqProc = None

        logging.info("TCOP: Start.")

        self._runDnsmasq()
        logging.info("TCOP: Level 2 nameserver started.")

    def dispose(self):
        self._stopDnsmasq()
        logging.info("TCOP: Terminated.")

    def get_l2_nameserver_port(self):
        return self.dnsPort

    def add_host_entry(self, domain, ip):
        pass

    def add_domain_nameserver(self):
        pass





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
        os.unlink(self.pidFile)
        os.unlink(self.cfgFile)
