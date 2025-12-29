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
    PLUGIN_ID = "lyrics_window"
    PLUGIN_NAME = _("Lyrics Window")
    PLUGIN_DESC = _(
        "On a freedesktop.org desktop (GNOME, KDE, Xfce, etc.), when a song is playing,"
        " prevents the computer from suspending."
    )
    PLUGIN_ICON = Icons.FORMAT_JUSTIFY_FILL

    CONFIG_WIDTH = PLUGIN_ID + "_width"
    CONFIG_HEIGHT = PLUGIN_ID + "_height"
    CONFIG_X = PLUGIN_ID + "_x"
    CONFIG_Y = PLUGIN_ID + "_y"

    _window = None

    class Win(Gtk.Window):
    #class Win(Window, util.InstanceTracker, PersistentWindowMixin):
        TEXT_CSS = '* { background-color: rgba(12, 8, 24, 0.5); color: rgba(255, 255, 200, 1); padding: 10px; }'.encode('utf-8')
        APP_CSS = '* { background-color: rgba(0, 0, 0, 0); }'.encode('utf-8')
        #APP_CSS = '* { background-color: transparent; }'.encode('utf-8')
        #APP_CSS = '* { background-color: rgba(12, 8, 24, 0.5); }'.encode('utf-8')

        GRAB_BORDER = 16  # リサイズ検出幅(px)

        scrolled_window = None
        # adjustment = None
        textview = None
        # textbuffer = None

        def __init__(self):
            Gtk.Window.__init__(self)
            self.set_decorated(False)
            self.set_skip_taskbar_hint(True)
            self.set_skip_pager_hint(True)
            self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
            self.set_destroy_with_parent(True)
            #self.set_focus_visible(False)
            self.connect("delete_event", self.on_destroy)

            x = config.getint("plugins", LyricsWindow.CONFIG_X, 2600)
            y = config.getint("plugins", LyricsWindow.CONFIG_Y, 0)
            width = config.getint("plugins", LyricsWindow.CONFIG_WIDTH, 550)
            height = config.getint("plugins", LyricsWindow.CONFIG_HEIGHT, 950)
            self.move(x, y)
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
            # self.adjustment = self.scrolled_window.get_vadjustment()
            self.textview = Gtk.TextView()
            # self.textbuffer = self.textview.get_buffer()
            self.textview.set_editable(False)
            self.textview.set_cursor_visible(False)
            self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
            #self.textview.set_justification(Gtk.Justification.CENTER)
            add_css(self.textview, self.TEXT_CSS)
            self.scrolled_window.add(self.textview)
            self.add(self.scrolled_window)

            #provider = Gtk.CssProvider()
            #provider.load_from_data(self.APP_CSS)
            #context = self.get_style_context()
            #context.add_provider_for_screen(self.textview.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            add_css(self, self.APP_CSS)

            # シグナルの処理
            self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                            Gdk.EventMask.POINTER_MOTION_MASK |
                            Gdk.EventMask.BUTTON_RELEASE_MASK)
            self.connect('button-press-event', self.on_button_press_event)
            self.connect("motion-notify-event", self.on_motion)
            #self.resize(self.pixbuf.get_width(), self.pixbuf.get_height())
            #self.show_all()
            self.activate()

        def update_lyrics(self, lyrics):
            ####### self.hide()
            buffer = self.textview.get_buffer()
            buffer.set_text(lyrics + "\n♬")

            start = buffer.get_start_iter()
            end = buffer.get_end_iter()
            table = buffer.get_tag_table()
            center_tag = table.lookup("center")
            if not center_tag:
                center_tag = Gtk.TextTag.new("center")
                center_tag.set_property("justification", Gtk.Justification.CENTER)
                table.add(center_tag)
            buffer.apply_tag(center_tag, start, end)

            # 最後の行開始を探す：末尾から最後の改行を検索
            # end is after last character; search backwards for '\n'
            search_iter = end.copy()
            found = search_iter.backward_search("\n", Gtk.TextSearchFlags.TEXT_ONLY, None)
            if found is None:
                # 改行なし＝全文が1行 → 行頭はバッファ先頭
                last_start = buffer.get_start_iter()
            else:
                # backward_search は (match_start, match_end) を返す
                match_start, match_end = found
                # 最後の改行の直後が最後の行の先頭
                last_start = match_end

            # もし末尾が改行で終わるなら最後の行は空行なので、その前の行を使う
            # if last_start.equal(end):
            #     # バッファ末尾が改行で終わる場合、前の改行をもう一度検索
            #     search_iter = last_start.copy()
            #     found2 = search_iter.backward_search("\n", Gtk.TextSearchFlags.TEXT_ONLY, None)
            #     if found2 is None:
            #         last_start = buf.get_start_iter()
            #     else:
            #         match_start2, match_end2 = found2
            #         last_start = match_end2

            right_tag = table.lookup("right")
            if not right_tag:
                right_tag = Gtk.TextTag.new("right")
                right_tag.set_property("justification", Gtk.Justification.RIGHT)
                table.add(right_tag)
            buffer.apply_tag(right_tag, last_start, end)

            # self.adjustment.set_value(0)  # Scroll to the top.
            # self.set_skip_taskbar_hint(True)
            # self.set_skip_pager_hint(True)
            self.textview.set_sensitive(True)
            self.scrolled_window.set_sensitive(True)
            self.set_sensitive(True)
            self.show_all()
            #self.activate()

        def on_destroy(self, widget, event):
            (x, y) = self.get_position()
            (width, height) = self.get_size()
            config.set("plugins", LyricsWindow.CONFIG_X, str(x))
            config.set("plugins", LyricsWindow.CONFIG_Y, str(y))
            config.set("plugins", LyricsWindow.CONFIG_WIDTH, str(width))
            config.set("plugins", LyricsWindow.CONFIG_HEIGHT, str(height))
            return

        def on_button_press_event(self, widget, event):
            '''
                マウスでどこを掴んでも移動できるように
                ダブルクリックで終了
            '''
            if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
                alloc = self.get_allocation()
                edge = self.get_edge_from_pos(event.x, event.y, alloc.width, alloc.height)
                if edge is None:
                    self.begin_move_drag(event.button, event.x_root, event.y_root, event.time)
                else:
                    self.begin_resize_drag(edge, event.button, event.x_root, event.y_root, event.time)

        def on_motion(self, widget, event):
            # カーソル形状を端で変更する（任意）
            alloc = self.get_allocation()
            edge = self.get_edge_from_pos(event.x, event.y, alloc.width, alloc.height)
            display = Gdk.Display.get_default()
            if edge is None:
                cursor_name = "move"
            else:
                # 簡易マッピング（名称は環境依存）
                mapping = {
                    Gdk.WindowEdge.NORTH: "ns-resize",
                    Gdk.WindowEdge.SOUTH: "ns-resize",
                    Gdk.WindowEdge.WEST: "ew-resize",
                    Gdk.WindowEdge.EAST: "ew-resize",
                    Gdk.WindowEdge.NORTH_WEST: "nwse-resize",
                    Gdk.WindowEdge.NORTH_EAST: "nesw-resize",
                    Gdk.WindowEdge.SOUTH_WEST: "nesw-resize",
                    Gdk.WindowEdge.SOUTH_EAST: "nwse-resize",
                }
                cursor_name = mapping.get(edge, "move")
            # try:
            cursor = Gdk.Cursor.new_from_name(display, cursor_name)
            #cursor.get_cursor_type()
            self.get_window().set_cursor(cursor)
            # except Exception:
            #     # 古い環境では new_from_name が無い場合もある
            #     pass
            #return False

        def get_edge_from_pos(self, x, y, width, height):
            left = x <= self.GRAB_BORDER
            right = x >= (width - self.GRAB_BORDER)
            top = y <= self.GRAB_BORDER
            bottom = y >= (height - self.GRAB_BORDER)

            # 角の優先順位：外側（角）があれば角を返す
            if left and top:
                return Gdk.WindowEdge.NORTH_WEST
            if right and top:
                return Gdk.WindowEdge.NORTH_EAST
            if left and bottom:
                return Gdk.WindowEdge.SOUTH_WEST
            if right and bottom:
                return Gdk.WindowEdge.SOUTH_EAST
            if top:
                return Gdk.WindowEdge.NORTH
            if bottom:
                return Gdk.WindowEdge.SOUTH
            if left:
                return Gdk.WindowEdge.WEST
            if right:
                return Gdk.WindowEdge.EAST
            return None

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
            else:
                if self._window:
                    self._window.close()
                    self._window = None

    def plugin_on_changed(self, songs):
        cur = app.player.info
        if cur:
            fn = cur("~filename")
            for s in songs:
                if s("~filename") == fn:
                    print_d("Active song changed, reloading lyrics")
                    self.plugin_on_song_started(SongWrapper(cur))
        else:
            if self._window:
                self._window.close()
                self._window = None
