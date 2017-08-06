#!/usr/bin/env python2
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import dbus
import json


dbusObj = dbus.SystemBus().get_object('org.fpemud.WRT', '/org/fpemud/WRT')
str = json.dumps(json.loads(dbusObj.GetRouterInfo()), indent=4, sort_keys=True)
print(str)

