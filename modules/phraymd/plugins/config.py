'''

    phraymd - Configuration Plugin
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
import gobject
import os

from phraymd import settings
from phraymd import pluginbase
from phraymd import pluginmanager
from phraymd import imageinfo
from phraymd import collectionmanager

class ConfigPlugin(pluginbase.Plugin):
    name='ConfigPlugin'
    display_name='Configuration Sidebar'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        print 'INITIALIZING CONFIGURATION PLUGIN'

    def plugin_init(self,mainframe,app_init):
        self.mainframe=mainframe
        self.config=None #defer creation until the dialog is requested (saves resources, faster startup)
#        self.mainframe.sidebar.append_page(self.config,gtk.Label("Configure"))

    def plugin_shutdown(self,app_shutdown):
        pass

    def app_config_dialog(self):
        if self.config==None:
            self.config=ConfigPanel(self)
        response=self.config.run()
        self.config.hide()
        return True


'''
Collection settings:
* Refresh collection startup (checkbox)
* Refresh collection now (button)
* Caching options (number of thumbnails, number of images)
Plugins
* List of plugins (checkbox disable)
Collections (List control or combo)
* List of collections (name, directory)
* Activate collection
Custom shell tools
* Tool name
* Command line
* Mimetype/Infotype
'''

class ConfigPanel(gtk.Dialog):
    def __init__(self,plugin):
        gtk.Dialog.__init__(self,flags=gtk.DIALOG_MODAL)
        self.plugin=plugin
        self.set_default_size(600,400)
        nb=gtk.Notebook()
        self.vbox.pack_start(nb)

        def page(nb,text,panel):
            page=gtk.ScrolledWindow()
            page.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
            page.add_with_viewport(panel)
            label=gtk.Label()
            label.set_markup('<b>'+text+'</b>')
            nb.append_page(page,label)
            return panel

        page(nb,"About",AboutBox())
        page(nb,"Collections",CollectionsBox(plugin))
        page(nb,"Plugins",PluginBox())
        page(nb,"Tools",ToolsBox())
        self.add_button("_Close",gtk.RESPONSE_ACCEPT)
        nb.show_all()
    def save_settings(self):
        pass
    def load_settings(self):
        pass

class ToolsBox(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)
        ##tool name, mimetype, command
        self.model=gtk.ListStore(gobject.TYPE_STRING,gobject.TYPE_STRING,gobject.TYPE_STRING)
        self.init_view()
        self.view=gtk.TreeView(self.model)
        self.pack_start(self.view)

        hbox=gtk.HBox()
        add_button = gtk.Button(stock=gtk.STOCK_ADD)
        add_button.connect('clicked', self.add_signal)
        delete_button = gtk.Button(stock=gtk.STOCK_REMOVE)
        delete_button.connect('clicked', self.delete_signal)
        hbox.pack_start(add_button,False)
        hbox.pack_start(delete_button,False)
        self.pack_start(hbox, False)

        name=gtk.CellRendererText()
        name.set_property("editable",True)
        #name.set_property('mode',gtk.CELL_RENDERER_MODE_EDITABLE) ##implicit in editable property?
        name.connect("edited",self.name_edited_signal)
        self.view.append_column(gtk.TreeViewColumn('Name',name,text=0))
        mime=gtk.CellRendererText()
        mime.set_property("editable",True)
        mime.connect("edited",self.mime_edited_signal)
        self.view.append_column(gtk.TreeViewColumn('Mimetype',mime,text=1))
        command=gtk.CellRendererText()
        command.set_property("editable",True)
        command.connect("edited",self.command_edited_signal)
        self.view.append_column(gtk.TreeViewColumn('Command',command,text=2))
        self.default_name='New Command'

    def init_view(self):
        self.model.clear()
        for mime,tools in settings.custom_launchers.iteritems():
            for tool in tools:
                self.model.append((tool[0],mime,tool[1]))

    def name_edited_signal(self, cellrenderertext, path, new_text):
        name,mime,cmd=self.model[path]
        if new_text==self.default_name:
            return
        if name==self.default_name:
            if mime in settings.custom_launchers:
                settings.custom_launchers[mime].append((new_text,cmd))
            else:
                settings.custom_launchers[mime]=[(new_text,cmd)]
            self.model[path][0]=new_text
            return
        for i in range(len(settings.custom_launchers[mime])):
            n,c=settings.custom_launchers[mime][i]
            if n==name and c==cmd:
                settings.custom_launchers[mime][i]=(new_text,c)
                break
        self.model[path][0]=new_text

    def mime_edited_signal(self, cellrenderertext, path, new_text):
        name,mime,cmd=self.model[path]
        if name==self.default_name:
            self.model[path][1]=new_text
            return
        for i in range(len(settings.custom_launchers[mime])):
            n,c=settings.custom_launchers[mime][i]
            if n==name and c==cmd:
                del settings.custom_launchers[mime][i]
                if len(settings.custom_launchers[mime])==0:
                    del settings.custom_launchers[mime]
                break
        if new_text not in settings.custom_launchers:
            settings.custom_launchers[new_text]=[(n,c)]
        else:
            settings.custom_launchers[new_text].append((n,c))
        self.model[path][1]=new_text

    def command_edited_signal(self, cellrenderertext, path, new_text):
        name,mime,cmd=self.model[path]
        if name==self.default_name:
            self.model[path][2]=new_text
            return
        for i in range(len(settings.custom_launchers[mime])):
            n,c=settings.custom_launchers[mime][i]
            if n==name and c==cmd:
                settings.custom_launchers[mime][i]=(n,new_text)
                break
        self.model[path][2]=new_text

    def add_signal(self, widget):
        self.model.append((self.default_name,'default',''))

    def delete_signal(self, widget):
        sel=self.view.get_selection()
        if not sel:
            return
        model,iter=sel.get_selected()
        if iter==None:
            return
        name,mime,cmd=self.model[iter]
        if name==self.default_name:
            self.model.remove(iter)
            return
        for i in range(len(settings.custom_launchers[mime])):
            n,c=settings.custom_launchers[mime][i]
            if n==name and c==cmd:
                del settings.custom_launchers[mime][i]
                if len(settings.custom_launchers[mime])==0:
                    del settings.custom_launchers[mime]
                break
        self.model.remove(iter)


class CollectionsBox(gtk.HBox):
    def __init__(self,plugin):
        gtk.HBox.__init__(self)
        ##tool name, mimetype, command
        self.plugin=plugin

        vbox_left=gtk.VBox()
        vbox_right=gtk.VBox()
        self.pack_start(vbox_left, False)
        self.pack_start(vbox_right)

        self.model=plugin.mainframe.coll_set.add_model('SELECTOR')
        self.view=gtk.TreeView(self.model)
        name=gtk.CellRendererText()
        name.set_property("editable",True)
        self.view.append_column(gtk.TreeViewColumn('Collections',name,text=collectionmanager.COLUMN_NAME,weight=collectionmanager.COLUMN_FONT_WGT))
        vbox_left.pack_start(self.view,True)

        hbox=gtk.HBox()
        add_button = gtk.Button(stock=gtk.STOCK_ADD)
#        add_button.connect('clicked', self.add_signal)
        delete_button = gtk.Button(stock=gtk.STOCK_REMOVE)
#        delete_button.connect('clicked', self.delete_signal)
        hbox.pack_start(add_button,False)
        hbox.pack_start(delete_button,False)
#        vbox_left.pack_start(hbox,False)


#    def name_edited_signal(self, cellrenderertext, path, new_text):
#        return
#        name=self.model[path]
#        if new_text==self.default_name:
#            return
#        if name==self.default_name:
#            if mime in settings.custom_launchers:
#                settings.custom_launchers[mime].append((new_text,cmd))
#            else:
#                settings.custom_launchers[mime]=[(new_text,cmd)]
#            self.model[path][0]=new_text
#            return
#        for i in range(len(settings.custom_launchers[mime])):
#            n,c=settings.custom_launchers[mime][i]
#            if n==name and c==cmd:
#                settings.custom_launchers[mime][i]=(new_text,c)
#                break
#        self.model[path][0]=new_text
#
#
#    def add_signal(self, widget):
#        name=self.plugin.mainframe.entry_dialog('New Collection','Name:')
#        if not name:
#            return
#        coll_dir=settings.user_add_dir()
#        if len(coll_dir)>0:
#            if imageinfo.create_empty_file(name,coll_dir):
#                self.model.append((name,400))
#
#    def delete_signal(self, widget):
#        sel=self.view.get_selection()
#        if not sel:
#            return
#        model,iter=sel.get_selected()
#        if iter==None:
#            return
#        name=self.model[iter][0]
#        if name==settings.active_collection:
#            return
#        try:
#            os.remove(os.path.join(settings.collections_dir,name))
#        except:
#            return
#        self.model.remove(iter)


class PluginBox(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)
        ##plugin name, plugin long name, version, enabled, can be disabled
        self.model=gtk.ListStore(gobject.TYPE_STRING,gobject.TYPE_STRING,gobject.TYPE_STRING,gobject.TYPE_BOOLEAN,gobject.TYPE_BOOLEAN)
        self.get_plugins()
        view=gtk.TreeView(self.model)
        self.pack_start(view)
        name=gtk.CellRendererText()
        view.append_column(gtk.TreeViewColumn('Name',name,text=1))
        version=gtk.CellRendererText()
        view.append_column(gtk.TreeViewColumn('Version',version,text=2))
        enable_toggle=gtk.CellRendererToggle()
        enable_toggle.connect('toggled',self.enable_toggle_signal)
        view.append_column(gtk.TreeViewColumn('Enabled',enable_toggle,active=3,activatable=4))

    def get_plugins(self):
        self.model.clear()
        for p,v in pluginmanager.mgr.plugins.iteritems():
            self.model.append((v[1].name,v[1].display_name,v[1].version,p not in settings.plugins_disabled,v[1]!=ConfigPlugin))

    def enable_toggle_signal(self,widget,path):
        plugin=self.model[path][0]
        if plugin in settings.plugins_disabled:
            del settings.plugins_disabled[settings.plugins_disabled.index(plugin)]
            pluginmanager.mgr.enable_plugin(plugin)
#            pluginmanager.mgr.callback_plugin(plugin,'plugin_init',pluginmanager.mgr.mainframe,False)
            self.model[path][3]=True
        else:
            settings.plugins_disabled.append(plugin)
            pluginmanager.mgr.disable_plugin(plugin)
            self.model[path][3]=False

class AboutBox(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self,False,10)
        pb=gtk.gdk.pixbuf_new_from_file(settings.icon_file)
        pb=pb.scale_simple(128,128,gtk.gdk.INTERP_BILINEAR)
        icon=gtk.image_new_from_pixbuf(pb)
        phraymd=gtk.Label()
        phraymd.set_markup('<b><big>phraymd</big></b>')
        version=gtk.Label('Version '+settings.release_version)
        author=gtk.Label('(C) Damien Moore 2010')
        contributors=gtk.Label('Contributors: antistress')
        help=gtk.Button('Get Help')
        help.connect('clicked',self.browser_open,'http://groups.google.com/group/phraymd')
        project=gtk.Button('Project Page')
        project.connect('clicked',self.browser_open,'https://launchpad.net/phraymd')
        bug=gtk.Button('Report a bug')
        bug.connect('clicked',self.browser_open,'https://bugs.launchpad.net/phraymd/+filebug')
        bb=gtk.HButtonBox()
        bl=gtk.HBox()
        br=gtk.HBox()
        hb=gtk.HBox()
        hb.pack_start(bl,True)
        hb.pack_start(bb,False)
        hb.pack_start(br,True)
        bb.pack_start(help,False,False,20)
        bb.pack_start(project,False,False,20)
        bb.pack_start(bug,False,False,20)
        self.pack_start(icon,False,False,10)
        widgets=(phraymd,version,author,contributors)
        for w in widgets:
            self.pack_start(w,False)
        self.pack_end(hb,False,False,10)
    def browser_open(self,widget,url):
        import webbrowser
        webbrowser.open(url)
