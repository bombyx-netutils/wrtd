#!/usr/bin/env python2
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import gi
gi.require_version("Jsonrpc", "1.0")
from gi.repository import Jsonrpc
from gi.repository import Gio

Gio.SocketConnection


client = Jsonrpc.Client()