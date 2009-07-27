#!/usr/bin/python

'''

    phraymd
    Copyright (C) 2009  Damien Moore

License:

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''


import sys
sys.path.insert(0,'/usr/share/phraymd') ##private module location on installed version -- todo: call the library phraymdlib

try:
    import gobject
    import gnomevfs
    import gtk
    import gnome.ui
    import pyexiv2
    gobject.threads_init()
    gtk.gdk.threads_init()
except:
    print 'ERROR: missing modules gobject, gtk, gnome.ui, gnomevfs and pyexiv2'
    import sys
    sys.exit()

from phraymd import settings
from phraymd import mainframe

settings.init() ##todo: make this call occur upon first import inside the settings module

class MainWindow:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_default_size(680, 400)
        self.window.set_title("phraymd")
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        sett=gtk.settings_get_default()
        sett.set_long_property("gtk-toolbar-icon-size",gtk.ICON_SIZE_SMALL_TOOLBAR,"phraymd:main") #gtk.ICON_SIZE_MENU
        sett.set_long_property("gtk-toolbar-style",gtk.TOOLBAR_ICONS,"phraymd:main")

        self.mainframe = mainframe.MainFrame()

        vb=gtk.VBox()
        vb.pack_start(self.mainframe)
        self.window.add(vb)

        self.window.show()
        vb.show()
        self.mainframe.show()

    def on_down(self, widget, data=None):
        self.browser.ScrollDown()

    def on_up(self, widget, data=None):
        self.browser.ScrollUp()

    def delete_event(self, widget, event, data=None):
        return False #allows the window to be destroyed

    def destroy(self, widget, data=None):
        print "destroy signal occurred"
        gtk.main_quit()

    def main(self):
        gtk.main()

if __name__ == "__main__":
    wnd = MainWindow()
    wnd.main()
