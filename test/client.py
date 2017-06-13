#!/usr/bin/env python2
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import gi
gi.require_version("Jsonrpc", "1.0")
from gi.repository import Jsonrpc
from gi.repository import GLib
from gi.repository import Gio


def callback1(source_object, result):
    global conn
    global gis
    global gos
    try:
        conn = source_object.connect_to_host_finish(result)
        gis = Gio.DataInputStream.new(conn.get_input_stream())
        gos = Gio.DataOutputStream.new(conn.get_output_stream())

        ret = gos.put_string("abc\n")
        assert ret

        gis.read_upto_async("\n", 1, 0, None, callback2)
    except GLib.Error:
        raise 

def callback2(source_object, result):
    try:
        msg, len = source_object.read_upto_finish(result)
        print("debug " + msg)
        source_object.read_byte()
        gis.read_upto_async("\n", 1, 0, None, callback2)
    except GLib.Error:
        raise 


mainloop = GLib.MainLoop()

sc = Gio.SocketClient.new()
sc.connect_to_host_async("127.0.0.1", 4458, None, callback1)

conn = None
gis = None
gos = None

mainloop.run()