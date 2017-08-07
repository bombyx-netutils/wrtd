#!/usr/bin/env python2
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import dbus
import json
import time


jsonObj = [
    {
        "facility-name": "test-gateway",
        "facility-type": "gateway",
        "target": [None, "eth0"],
        "network-list": ["18.0.0.0/255.0.0.0"],
    },
    {
        "facility-name": "test-nameserver",
        "facility-type": "nameserver",
        "target": ["8.8.8.8"],
        "domain-list": ["google.com"],
    },
]

dbusObj = dbus.SystemBus().get_object('org.fpemud.WRT', '/org/fpemud/WRT')
dbusObj.AddTrafficFacilityGroup("test", 0, json.dumps(jsonObj))

# so you can check the route and dnsmasq configuration
time.sleep(100)


