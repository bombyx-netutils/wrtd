#!/usr/bin/env python2
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import dbus


dbusObj = dbus.SystemBus().get_object('org.fpemud.WRT', '/org/fpemud/WRT')

print("Interface: ")
print("    " + dbusObj.GetInterface())
print("")

print("Prefix List: ")
for ip, mask in dbusObj.GetPrefixList():
    print("    " + ip + " " + mask)
print("")
