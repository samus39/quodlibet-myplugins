# Copyright 2011 Christoph Reiter <reiter.christoph@gmail.com>
# Copyright 2020 Antigone <mail@antigone.xyz>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os
import sys

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk

from quodlibet import _
from quodlibet import app
from quodlibet import config
from quodlibet.qltk import Icons
from quodlibet.plugins.events import EventPlugin

import re

from quodlibet import print_d
from quodlibet import qltk
from quodlibet.plugins.gui import UserInterfacePlugin
from quodlibet.qltk import add_css
from quodlibet.qltk.ccb import ConfigCheckButton
from quodlibet.qltk.information import Information
from quodlibet.util.songwrapper import SongWrapper

class LyricsWindow(EventPlugin):
    PLUGIN_ID = "lyrics_window_old"
    PLUGIN_NAME = _("Lyrics Window OLD")
    PLUGIN_DESC = _(
        "On a freedesktop.org desktop (GNOME, KDE, Xfce, etc.), when a song is playing,"
        " prevents the computer from suspending."
    )
    PLUGIN_ICON = Icons.FORMAT_JUSTIFY_FILL

    _window = None
    _position = None
    _size = None

    class Win(Gtk.Window):
    #class Win(Window, util.InstanceTracker, PersistentWindowMixin):
        TEXT_CSS = '* { background-color: rgba(8, 8, 16, 0.5); color: rgba(255, 255, 255, 1); }'.encode('utf-8')
        APP_CSS = '* { background-color: rgba(0, 0, 0, 0); }'.encode('utf-8')

        scrolled_window = None
        adjustment = None
        textview = None
        textbuffer = None
        _position = (2600, 0)
        _size = (550, 950)

        def __init__(self):
            #Gtk.Window.__init__(self, app_paintable=False, decorated=True)
            #Gtk.Window.__init__(self, app_paintable=True, decorated=True, type=Gtk.WindowType.TOPLEVEL)
            Gtk.Window.__init__(self)
            #super().__init__(dialog=False)
            self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
            self.set_destroy_with_parent(True)
            #self.set_focus_visible(False)
            self.connect("delete_event", self.on_destroy)
            if self._position:
                (x, y) = self._position
                self.move(x, y)
            if self._size:
                (width, height) = self._size
                self.resize(width, height)

            # 背景透過可能か確認、現行 GNOME が動く環境なら問題ないはずですが
            screen = self.get_screen()
            visual = screen.get_rgba_visual()
            if visual != None and screen.is_composited():
                self.set_visual(visual)

            self.scrolled_window = Gtk.ScrolledWindow()
            self.scrolled_window.set_policy(
                Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
            )
            #add_css(self.scrolled_window, self.APP_CSS)
            self.adjustment = self.scrolled_window.get_vadjustment()
            self.textview = Gtk.TextView()
            self.textbuffer = self.textview.get_buffer()
            self.textview.set_editable(False)
            self.textview.set_cursor_visible(False)
            self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
            self.textview.set_justification(Gtk.Justification.CENTER)
            #add_css(self.textview, "* { padding: 6px; }")
            add_css(self.textview, self.TEXT_CSS)
            self.scrolled_window.add(self.textview)
            self.add(self.scrolled_window)
            #self.textview.show()
            #self.scrolled_window.show()

            #provider = Gtk.CssProvider()
            #provider.load_from_data(self.APP_CSS)
            #context = self.get_style_context()
            #context.add_provider_for_screen(self.textview.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            add_css(self, self.APP_CSS)

            # シグナルの処理
            self.connect('button-press-event', self.on_button_press_event)
            #self.resize(self.pixbuf.get_width(), self.pixbuf.get_height())
            #self.show_all()
            self.activate()

        def update_lyrics(self, lyrics):
            self.hide()
            self.textbuffer.set_text(lyrics)
            self.adjustment.set_value(0)  # Scroll to the top.
            #start_iter = self.textbuffer.get_start_iter()
            #end_iter = self.textbuffer.get_end_iter()
            self.show_all()
            self.textview.set_sensitive(True)
            self.scrolled_window.set_sensitive(True)
            self.set_sensitive(True)
            self.activate()
            #self.activate_focus()
            #self.present()

        def on_destroy(self, widget, event):
            self._position = self.get_position()
            self._size = self.get_size()
            return

        def on_button_press_event(self, widget, event):
            '''
                マウスでどこを掴んでも移動できるように
                ダブルクリックで終了
            '''
            if event.type == Gdk.EventType.BUTTON_PRESS:
                self.begin_move_drag(event.button, event.x_root, event.y_root, event.time)

    def enabled(self):
        cur = app.player.info
        if cur:
            self.plugin_on_song_started(SongWrapper(cur))

    def disabled(self):
        if self._window:
            self._window.close()
            self._window = None

    def plugin_on_song_started(self, song):
        """Called when a song is started. Loads the lyrics.

        If there are lyrics associated with `song`, load them into the
        lyrics viewer. Otherwise, hides the lyrics viewer.
        """
        lyrics = None
        if song is not None:
            print_d("Looking for lyrics for {}".format(song("~filename")))
            lyrics = song("~lyrics")
            if lyrics:
                if self._window is None:
                    self._window = self.Win()
                self._window.update_lyrics(lyrics)

    def plugin_on_changed(self, songs):
        cur = app.player.info
        if cur:
            fn = cur("~filename")
            for s in songs:
                if s("~filename") == fn:
                    print_d("Active song changed, reloading lyrics")
                    self.plugin_on_song_started(SongWrapper(cur))
