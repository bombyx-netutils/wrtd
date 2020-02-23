#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-


# config file: ${ETC}/wan-connection.json
# only allow one plugin be loaded
# must set an all deny firewall rule for the out interface before wan connection is up
class TemplatePlugin:

    def init2(self, tmpDir, ownResolvConf, upCallback, downCallback):
        # upCallback:
        #   is_alive() should return True in upCallback().
        #   exception raised by upCallback() would make the plugin bring down the connection.
        # downCallback:
        #   is_alive() should return False in downCallback().
        #   no exception is allowed in downCallback().
        assert False

    def get_interface(self):
        # always returns valid value
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def is_connected(self):
        assert False

    def get_ip(self):
        assert False

    def get_netmask(self):
        assert False

    def get_extra_prefix_list(self):
        # returns [(ip, mask), (ip,mask ), ...]
        assert False

    def get_business_attributes(self):
        # returns technical related business attributes:
        # {
        #    "bandwidth": 10,           # unit: KB/s, no key means bandwidth is unknown
        #    "billing": "traffic",      # values: "traffic" or "time", no key means no billing
        # }
        assert False

    def interface_appear(self, ifname):
        # return True means we take this interface
        # must be called after start()
        assert False

    def interface_disappear(self, ifname):
        # must be called after start()
        assert False


class TemplatePluginApi:

    def activated(self, internet_ip, prefix_list, gateway, route_list):
        pass

    def deactivated(self):
        pass

        # upCallback:
        #   is_alive() should return True in upCallback().
        #   exception raised by upCallback() would make the plugin bring down the connection.
        # downCallback:
        #   is_alive() should return False in downCallback().
        #   no exception is allowed in downCallback().
