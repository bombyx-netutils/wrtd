#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

# plugin module name: plugins.vpns_*
# config file: ${ETC}/vpn-server-(PLUGIN_NAME)-(INSTANCE_NAME).json
# allow multiple plugins be loaded, and one plugin can have multiple instances
class TemplatePluginVpnServer:

    def init2(self, instanceName, cfg, tmpDir, varDir, bridgePrefix, l2DnsPort, clientAddCallback, clientChangeCallback, clientRemoveCallback):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def get_bridge(self):
        # must be called after start()
        assert False

    def get_wan_service(self):
        assert False


class TemplatePluginApi:

    def get_tmp_dir(self):
        pass

    def get_var_dir(self):
        pass

    def get_bridge(self):
        pass

    def get_reserved_interfaces(self, ifindex_list):
        pass
