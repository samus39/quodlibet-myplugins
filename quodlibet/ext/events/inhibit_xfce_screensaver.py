# Copyright 2011 Christoph Reiter <reiter.christoph@gmail.com>
# Copyright 2020 Antigone <mail@antigone.xyz>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os
import sys

if os.name == "nt" or sys.platform == "darwin":
    from quodlibet.plugins import PluginNotSupportedError
    raise PluginNotSupportedError

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from quodlibet import _
from quodlibet import app
from quodlibet import config
from quodlibet.qltk import Icons
from quodlibet.plugins.events import EventPlugin

class InhibitXfceScreensaver(EventPlugin):
    PLUGIN_ID = "inhibit_xfce_screensaver"
    PLUGIN_NAME = _("Inhibit Xfce Screensaver")
    PLUGIN_DESC = _(
        "On a Xfce desktop, when a song is playing,"
        " prevents either the screensaver from activating."
    )
    PLUGIN_ICON = Icons.PREFERENCES_DESKTOP_SCREENSAVER

    DBUS_NAME = "org.xfce.ScreenSaver"
    DBUS_INTERFACE = "org.xfce.ScreenSaver"
    DBUS_PATH = "/org/xfce/ScreenSaver"

    APPLICATION_ID = "quodlibet"
    INHIBIT_REASON = _("Music is playing")

    __cookie = None

    def __get_dbus_proxy(self):
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            self.DBUS_NAME,
            self.DBUS_PATH,
            self.DBUS_INTERFACE,
            None,
        )

    def enabled(self):
        if not app.player.paused:
            self.plugin_on_unpaused()

    def disabled(self):
        if not app.player.paused:
            self.plugin_on_paused()

    def plugin_on_unpaused(self):
        try:
            dbus_proxy = self.__get_dbus_proxy()
            self.__cookie = dbus_proxy.Inhibit(
                "(ss)", self.APPLICATION_ID, self.INHIBIT_REASON
            )
        except GLib.Error:
            pass

    def plugin_on_paused(self):
        if self.__cookie is None:
            return

        try:
            dbus_proxy = self.__get_dbus_proxy()
            dbus_proxy.UnInhibit("(u)", self.__cookie)
            self.__cookie = None
        except GLib.Error:
            pass
