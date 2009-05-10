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

import gtk
import imageinfo


## provides gui elements for working with tags
## 1. tree interface for choosing tags to "paint" onto  images
## 2. tag selector dialog
## 3. tag auto-completer
## tag collection object (keeps track of available tags and counts)

class TagFrame(gtk.VBox):
    def __init__(self,worker,browser):
        gtk.VBox.__init__(self)
        self.worker=worker
        self.browser=browser
        self.model=gtk.TreeStore(str,gtk.gdk.Pixbuf,str,'gboolean')
        self.tv=gtk.TreeView(self.model)
        self.tv.set_reorderable(True)
        self.tv.set_headers_visible(False)
        self.tv.connect("row-activated",self.tag_activate)
        tvc_bitmap=gtk.TreeViewColumn(None,gtk.CellRendererPixbuf(),pixbuf=1)
        tvc_text=gtk.TreeViewColumn(None,gtk.CellRendererText(),text=2)
        toggle=gtk.CellRendererToggle()
        toggle.set_property("activatable",True)
        toggle.connect("toggled",self.toggle_signal)
        tvc_check=gtk.TreeViewColumn(None,toggle,active=3)
        ##gtk.CellRendererText
        self.tv.append_column(tvc_check)
        self.tv.append_column(tvc_bitmap)
        self.tv.append_column(tvc_text)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.add_with_viewport(self.tv)
        scrolled_window.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        self.pack_start(scrolled_window)
#        self.model.append(None,(None,'test',False))

    def tag_activate(self,treeview, path, view_column):
        self.browser.filter_entry.set_text('view:tag="%s"'%self.model[path][0])
        self.browser.filter_entry.activate()

    def toggle_signal(self,cellrenderertoggle, path):
        self.model[path][2]=not self.model[path][2]
    def refresh(self,tag_cloud):
        self.model.clear()
        for k in tag_cloud.tags:
            self.model.append(None,(k,None,k+' (%i)'%(tag_cloud.tags[k],),False))

if __name__=='__main__':
    window = gtk.Window()
    tree = TagFrame()
    vertical_box = gtk.VBox(False, 6)
    button_box = gtk.HButtonBox()
    insert = gtk.Button('Tag Images')
    description = gtk.Button('Untag Images')

    vertical_box.pack_start(tree)
    vertical_box.pack_start(button_box, False, False)
    button_box.pack_start(insert)
    button_box.pack_start(description)
    window.add(vertical_box)

#    insert.connect('clicked', insert_item)
#    description.connect('clicked', show_description)
    window.connect('destroy', lambda window: gtk.main_quit())

    window.resize(400, 500)
    window.show_all()

    gtk.main()
