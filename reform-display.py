#!/usr/bin/env python3

import os
import sys
import struct
import argparse

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
import cairo
import math


####
buffer_width = 126
buffer_height = 32

def program_kbd(argb_data):
    return
    cmd = 'xWBIT'
    path = '/dev/hidraw3'

    def write_str(f, str):
        f.write(struct.pack('={0}s'.format(len(str)), str.encode()))

    def write_byte(f, b):
        f.write(struct.pack('=B', b))

    with open(path, 'wb') as f:
        write_str(f, cmd)
        for y_line in range(0, buffer_height // 8):
            for x in range(0, buffer_width):
                b_column = 0
                for y_pixel in range(0, 8):
                    offset = ((y_pixel + y_line * 8) * buffer_width + x) * 4
                    val = (1 << y_pixel) if argb_data[offset + 2] != 0 else 0
                    b_column = b_column | val
                write_byte(f, b_column)
        f.close()

####
Gio.resources_register(Gio.resource_load('org.mnt.ReformDisplay.gresource'));
b = Gtk.Builder.new_from_resource('/org/mnt/Reform/ReformDisplay.ui');

def o(name):
    return b.get_object(name)

####
draw_buffer = bytearray(4 * buffer_width * buffer_height)
has_update = False

cairo_surf = cairo.ImageSurface(cairo.Format.ARGB32, buffer_width, buffer_height)

ctx = cairo.Context(cairo_surf)

####
class StaticText(object):
    def __init__(self, text, x, y, w):
        self.text = text
        self.x = x
        self.y = y
        self.w = w

    def render(self, ctx, offset):
        ctx.translate(self.x, self.y)
        text_ext = ctx.text_extents(self.text)
        ctx.show_text(self.text)

class RotatingText(object):
    def __init__(self, text, x, y, w):
        self.text = text
        self.x = x
        self.y = y
        self.w = w

    def render(self, ctx, offset):
        ctx.translate(self.x, self.y)
        text_ext = ctx.text_extents(self.text)
        ctx.rectangle(0, text_ext.y_bearing, self.w, text_ext.height)
        ctx.clip()
        offset %= text_ext.width
        ctx.translate(-offset, 0)
        ctx.show_text(self.text)

        if (text_ext.width - offset) < self.w:
            ctx.translate(text_ext.width + offset, 0)
            ctx.show_text(self.text)


rots = [StaticText('MNT Reform', 24, 9, 100),
        RotatingText('abcdefghijklmnopqrstuvwxyz', 0, 21, 132)]

def update_image():
    scale = int(o('adjustment1').get_value())

    img_surf = cairo.ImageSurface(cairo.Format.ARGB32,
                                  buffer_width * scale,
                                  buffer_height * scale)

    ctx = cairo.Context(img_surf)
    ctx.save()
    ctx.set_antialias(cairo.ANTIALIAS_NONE)
    ctx.scale(scale, scale)
    ctx.rectangle(0, 0, buffer_width * scale, buffer_height * scale)
    ctx.set_source_surface(cairo_surf)
    ctx.fill()
    ctx.restore()
    o('draw-image').set_from_surface(img_surf)


####
offset = 0
def maybe_redraw():
    global offset
    ctx.save()

    # Clear
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.rectangle(0, 0, buffer_width, buffer_height)
    ctx.fill()

    ctx.set_antialias(cairo.ANTIALIAS_NONE)
    ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.select_font_face("Bitstream", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(10)
    for r in rots:
        ctx.save()
        r.render(ctx, offset * 2)
        ctx.restore()

    ctx.restore()

    update_image()
    program_kbd(cairo_surf.get_data())
    offset += 1
    return True

GLib.timeout_add(200, maybe_redraw)

def dbus_start():

    def update_playing_metadata(metadata):
        title = metadata['xesam:title'] if 'xesam:title' in metadata else 'Unknown'
        artist = metadata['xesam:artist'] if 'xesam:artist' in metadata else 'Unknown'
        if isinstance(artist, list):
            artist = ' '.join(artist)
        rots[1].text = 'Playing {0} by {1}  '.format(title, artist)

    def on_media_message(conn, sender_name, object_path, interface_name, signal_name, parameters):
        if parameters[0] != 'org.mpris.MediaPlayer2.Player':
            return
        for p in parameters:
            if not isinstance(p, dict):
                continue

            for k,v in p.items():
                if k != 'Metadata':
                    continue
                update_playing_metadata(v)

    def on_battery_message(conn, sender_name, object_path, interface_name, signal_name, parameters):
        print(parameters)

    def read_battery_init(conn):
        proxy = Gio.DBusProxy.new_sync(conn,
                                       Gio.DBusProxyFlags.NONE,
                                       None, # info
                                       'org.freedesktop.UPower',
                                       '/org/freedesktop/UPower/devices/battery_BAT0',
                                       'org.freedesktop.DBus.Properties',
                                       None) # cancellable
        return proxy.Get('(ss)', 'org.freedesktop.UPower.Device', 'Percentage')


    sess_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    sess_bus.signal_subscribe(None, # sender
                              'org.freedesktop.DBus.Properties',
                              'PropertiesChanged',
                              '/org/mpris/MediaPlayer2',
                              None, # arg0
                              Gio.DBusSignalFlags.NONE,
                              on_media_message)
    sys_bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    print('bat = {0}'.format(read_battery_init(sys_bus)))
    uid = sys_bus.signal_subscribe('org.freedesktop.UPower',
                                   'org.freedesktop.DBus.Properties',
                                   'PropertiesChanged',
                                   '/org/freedesktop/UPower/devices/battery_BAT0', # object_path
                                   None, # arg0
                                   Gio.DBusSignalFlags.NONE,
                                   on_battery_message)

#    print(uid)
#    connection.add_filter(on_dbus_message)


def on_clear(button):
    global draw_buffer
    draw_buffer = bytearray(4 * buffer_width * buffer_height)
    #write_string(0, 0, 'MNT Reform')
    has_update = True
    program_kbd(draw_buffer)

def main():
    # … create a new window…
    o('window').connect('destroy', lambda x: Gtk.main_quit())
    o('window').show()

    #
    update_image()

    o('clear-button').connect('clicked', on_clear)

    Gtk.main()

if __name__ == '__main__':
    dbus_start()
    main()
