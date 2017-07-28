#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-


class TemplateBridge:

    def get_name(self):
        assert False

    def get_prefix(self):
        # returns (ip, mask)
        assert False

    def get_bridge_id(self):
        assert False

    def on_source_add(self, source_id):
        assert False

    def on_source_remove(self, source_id):
        assert False

    def on_host_add(self, source_id, ip_data_dict):
        assert False

    def on_host_change(self, source_id, ip_data_dict):
        assert False

    def on_host_remove(self, source_id, ip_list):
        assert False

    def on_host_refresh(self, source_id, ip_data_dict):
        assert False


# plugin module name: plugins.wconn_*
# config file: ${ETC}/wan-connection.json
# only allow one plugin be loaded
# must set an all deny firewall rule for the out interface immediately after wan connection is up
class PluginTemplateWanConnection:

    def init2(self, tmpDir, ownResolvConf, upCallback, downCallback):
        # upCallback:
        #   is_alive() should return True in upCallback().
        #   exception raised by upCallback() would make the plugin bring down the connection.
        # downCallback:
        #   is_alive() should return False in downCallback().
        #   no exception is allowed in downCallback().
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def is_connected(self):
        assert False

    def get_ip(self):
        assert False

    def get_interface(self):
        assert False

    def get_prefix_list(self):
        # returns [(ip, mask), (ip,mask ), ...]
        assert False

    def interface_appear(self, ifname):
        # return True means we take this interface
        # must be called after start()
        assert False

    def interface_disappear(self, ifname):
        # must be called after start()
        assert False

# plugin module name: plugins.lif_*
# config file: ${ETC}/lan-interface-(PLUGIN_NAME)-(INSTANCE_NAME).json
# allow multiple plugins be loaded, and one plugin can have multiple instances
class TemplatePluginLanInterface:

    def init2(self, instanceName, cfg, tmpDir, varDir):
        assert False

    def start(self):
        assert False

    def stop(self):
        assert False

    def interface_appear(self, bridge, ifname):
        # return True means we take this interface
        # must be called after start()
        assert False

    def interface_disappear(self, ifname):
        # must be called after start()
        assert False


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

    def generate_client_script(self, wan_ip, os_type):
        # returns (suggested-script-filename, script-content)
        assert False


# plugin module name: plugins.manager_*
# config file: ${ETC}/manager-(PLUGIN_NAME).json
# manager unload is not supported, so manager_disappear() is not needed
class TemplatePluginManager:

    def init2(self, cfg, etcDir, tmpDir, varDir, pluginManagerData):
        assert False

    def manager_appear(self, name, manager):
        assert False


class TemplatePluginManagerData:

    @property
    def uuid(self):
        assert False

    @property
    def plugin_hub(self):
        assert False

    @property
    def prefix_pool(self):
        assert False

    @property
    def managet_caller(self):
        assert False

    @property
    def traffic_manager(self):
        assert False

    @property
    def wan_manager(self):
        assert False

    @property
    def lan_manager(self):
        assert False


# template for json object
class TemplateFacilityNameserver:

    @property
    def facility_name(self):
        assert False

    @property
    def facility_type(self):
        return "nameserver"

    @property
    def target(self):
        """[(hostname,port)]"""
        assert False

    @property
    def domain_list(self):
        assert False


# template for json object
class TemplateFacilityGateway:

    @property
    def facility_name(self):
        assert False

    @property
    def facility_type(self):
        return "gateway"

    @property
    def target(self):
        """(next-hop,interface), invalid if both is None"""
        assert False

    @property
    def network_list(self):
        assert False


# template for json object
class TemplateFacilityHttpProxy:

    """HTTP/HTTPS/FTP proxy"""

    @property
    def facility_name(self):
        assert False

    @property
    def facility_type(self):
        return "http-proxy"

    @property
    def target(self):
        """{"http":(hostname, port),"https":(hostname,port),"ftp":(hostname,port)}"""
        assert False

    @property
    def domain_list(self):
        assert False


# template for json object
class TemplateLanService:

    @property
    def protocol(self):
        assert False

    @property
    def port(self):
        assert False

    @property
    def txt_dict(self):
        assert False


# template for json object
class TemplateWanService:

    @property
    def firewall_allow_list(self):
        assert False
