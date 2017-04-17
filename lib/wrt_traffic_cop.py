#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

class WrtTrafficCop:

    def __init__(self, param):
        self.param = param

        logging.info("TCOP: Start.")

    def dispose(self):
        logging.info("TCOP: Terminated.")
