import gtk
import gobject
import os

from phraymd import settings
from phraymd import pluginbase
from phraymd import pluginmanager
from phraymd import imageinfo

class ConfigPlugin(pluginbase.Plugin):
    name='ConfigPlugin'
    display_name='Configuration Sidebar'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        print 'INITIALIZING CONFIGURATION PLUGIN'

    def plugin_init(self,mainframe,app_init):
        self.mainframe=mainframe
        self.config=ConfigPanel(self)
        self.mainframe.sidebar.append_page(self.config,gtk.Label("Configure"))

    def plugin_shutdown(self,app_shutdown):
        pass


class ConfigPanel(gtk.ScrolledWindow):
    def __init__(self,plugin):
        gtk.ScrolledWindow.__init__(self)
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
        self.plugin=plugin
        main_box=gtk.VBox()
        self.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        self.add_with_viewport(main_box)

        def frame(text):
            frame=gtk.Frame()
            label=gtk.Label()
            label.set_markup('<b>'+text+'</b>')
            frame.set_label_widget(label)
            return frame

        collection_settings_frame=frame('Collection Settings')
        collections_frame=frame('Collections')
        collections_frame.add(CollectionsBox(self.plugin))
        plugins_frame=frame('Plugins')
        plugins_frame.add(PluginBox())
        tools_frame=frame('Tools')
        tools_frame.add(ToolsBox())
        main_box.pack_start(collection_settings_frame)
        main_box.pack_start(collections_frame)
        main_box.pack_start(plugins_frame)
        main_box.pack_start(tools_frame)
        self.show_all()
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


class CollectionsBox(gtk.VBox):
    def __init__(self,plugin):
        gtk.VBox.__init__(self)
        ##tool name, mimetype, command
        self.model=gtk.ListStore(gobject.TYPE_STRING,gobject.TYPE_INT)
        self.init_view()
        self.view=gtk.TreeView(self.model)
        self.pack_start(self.view)
        self.plugin=plugin

        hbox=gtk.HBox()
        open_button = gtk.Button(stock=gtk.STOCK_OPEN)
        open_button.connect('clicked', self.open_signal)
        add_button = gtk.Button(stock=gtk.STOCK_ADD)
        add_button.connect('clicked', self.add_signal)
        delete_button = gtk.Button(stock=gtk.STOCK_REMOVE)
        delete_button.connect('clicked', self.delete_signal)
        hbox.pack_start(open_button,False)
        hbox.pack_start(add_button,False)
        hbox.pack_start(delete_button,False)
        self.pack_start(hbox, False)

        name=gtk.CellRendererText()
        name.set_property("editable",True)
        self.view.append_column(gtk.TreeViewColumn('Name',name,text=0,weight=1))

    def init_view(self):
        self.model.clear()
        for col_file in settings.get_collection_files():
            if os.path.join(settings.collections_dir,col_file)==settings.active_collection_file:
                self.model.append((col_file,800))
            else:
                self.model.append((col_file,400))

    def name_edited_signal(self, cellrenderertext, path, new_text):
        return
        name=self.model[path]
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

    def activate_signal(self, widget, path):
        pass

    def open_signal(self,widget):
        sel=self.view.get_selection()
        if not sel:
            return
        model,iter=sel.get_selected()
        if iter==None:
            return
        for row in model:
            if row[1]==800:
                row[1]=400
        self.plugin.mainframe.tm.load_collection(os.path.join(settings.collections_dir,model[iter][0]))
        model[iter][1]=800

    def add_signal(self, widget):
        name=self.plugin.mainframe.entry_dialog('New Collection','Name:')
        if not name:
            return
        coll_dir=settings.user_add_dir()
        if len(coll_dir)>0:
            if imageinfo.create_empty_file(name,coll_dir):
                self.model.append((name,400))

    def delete_signal(self, widget):
        sel=self.view.get_selection()
        if not sel:
            return
        model,iter=sel.get_selected()
        if iter==None:
            return
        name=self.model[iter][0]
        if name==settings.active_collection:
            return
        try:
            os.remove(os.path.join(settings.collections_dir,name))
        except:
            return
        self.model.remove(iter)


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
            self.model.append((v[0].name,v[0].display_name,v[0].version,p not in settings.plugins_disabled,v[1]!=ConfigPlugin))

    def enable_toggle_signal(self,widget,path):
        plugin=self.model[path][0]
        if plugin in settings.plugins_disabled:
            del settings.plugins_disabled[settings.plugins_disabled.index(plugin)]
            pluginmanager.mgr.enable_plugin(plugin)
            pluginmanager.mgr.callback_plugin(plugin,'app_ready',pluginmanager.mgr.mainframe)
            self.model[path][3]=True
        else:
            settings.plugins_disabled.append(plugin)
            pluginmanager.mgr.disable_plugin(plugin)
            self.model[path][3]=False
