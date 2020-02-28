#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

# template metadata.xml
"""
<?xml version="1.0" encoding="utf-8"?>
<plugin>
  <lan-interface id="ethernet">
    <description>WAN connection by static configuration</description>
    <filename>plugin.py</filename>
    <classname>PluginObject</classname>
    <bridge>default</bridge>
  </lan-interface>
</plugin>
"""

# config file: ${ETC}/lan-interface-(PLUGIN_NAME)-(INSTANCE_NAME).json
# allow multiple plugins be loaded, and one plugin can have multiple instances
class TemplatePluginLanInterface:

    def init2(self, instanceName, cfgObj, api):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_bridge(self):
        assert False

    def get_managed_interfaces(self):
        assert False


class TemplatePluginApi:

    def get_tmp_dir(self):
        pass

    def get_var_dir(self):
        pass

    def get_bridge(self):
        pass

    def is_interface_reserved(self, ifindex):
        pass
