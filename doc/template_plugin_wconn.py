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

    def activate_interface(self, ifname, ifconfig):
        # Returns interface configuration.
        # must not be called in event callback
        # Example:
        # {
        #     "prefix": "10.254.1.155/24",
        #     "gateway": "121.33.99.247",         # optional
        #     "nameservers": [                    # optional
        #         "10.202.72.118",
        #         "10.202.72.119",
        #     ],
        #     "routes": [                         # optional
        #         {
        #             "prefix": "10.0.0.0/8",
        #             "gateway": "10.254.7.247",
        #         },
        #     ],
        #     "internet-ip": "121.33.97.55",      # optional
        #     "business-attributes": {            # optional
        #         "bandwidth": 10,                # unit: KB/s, no key means bandwidth is unknown
        #         "billing": "traffic",           # values: "traffic" or "time", no key means no billing
        #     },
        # }
        pass

    def deactive_interface(self, ifname):
        # must not be called in event callback
        # no need to call after interface is disappeared
        pass
