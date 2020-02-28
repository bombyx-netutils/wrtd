#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

# template metadata.xml
"""
<?xml version="1.0" encoding="utf-8"?>
<plugin>
  <wan-connection id="static">
    <description>WAN connection by static configuration</description>
    <filename>plugin.py</filename>
    <classname>PluginObject</classname>
  </wan-connection>
</plugin>
"""


# config file: ${ETC}/wan-connection.json
# only allow one plugin be loaded
class TemplatePlugin:

    def start(self, cfgObj, api):
        assert False

    def stop(self):
        assert False


class TemplatePluginApi:

    def get_tmp_dir(self):
        pass

    def get_var_dir(self):
        pass

    def reserve_interface(self, ifmatch_pattern):
        # ifname_pattern is to be used by fnmatch.fnmatch()
        pass

    def tfac_list_changed(self, tfac_list):
        pass

    def public_ip_changed(self, public_ip):
        pass
