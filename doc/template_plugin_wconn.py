#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-


# config file: ${ETC}/wan-connection.json
# only allow one plugin be loaded
class TemplatePlugin:

    def start(self, cfgObj, api):
        assert False

    def stop(self):
        assert False

    def interface_appear(self, ifname):
        # return True means we take this interface
        # must be called after start()
        assert False

    def interface_disappear(self, ifname):
        # must be called after start()
        assert False


class TemplatePluginApi:

    def get_tmp_dir(self):
        pass

    def reserve_interface(self, ifname_pattern):
        # ifname_pattern is to be used by fnmatch.fnmatch()
        pass

    def ntfac_changed(self, facility_list):
        pass

    def public_ip_changed(self, public_ip):
        pass
