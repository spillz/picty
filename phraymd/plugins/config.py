import gtk
import gobject

from phraymd import settings
from phraymd import pluginbase
from phraymd import pluginmanager

class ConfigPlugin(pluginbase.Plugin):
    name='ConfigPlugin'
    display_name='Configuration Sidebar'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        print 'INITIALIZING CONFIGURATION PLUGIN'
    def plugin_init(self,mainframe,app_init):
        self.mainframe=mainframe
        self.config=ConfigPanel()
        self.mainframe.sidebar.append_page(self.config,gtk.Label("Configure"))
    def plugin_shutdown(self,app_shutdown):
        pass


class ConfigPanel(gtk.ScrolledWindow):
    def __init__(self):
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
        main_box=gtk.VBox()
        self.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        self.add_with_viewport(main_box)

        collection_settings_frame=gtk.Frame('Collection Settings')
        collections_frame=gtk.Frame('Collections')
        plugins_frame=gtk.Frame('Plugins')
        plugins_frame.add(PluginBox())
        tools_frame=gtk.Frame('Tools')
        tools_frame.add(ToolsBox())
        main_box.pack_start(collection_settings_frame)
        main_box.pack_start(collections_frame)
        main_box.pack_start(plugins_frame)
        main_box.pack_start(tools_frame)
        self.show_all()
        pass
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
        view=gtk.TreeView(self.model)
        self.pack_start(view)
        name=gtk.CellRendererText()
        name.set_property("editable",True)
        #name.set_property('mode',gtk.CELL_RENDERER_MODE_EDITABLE) ##implicit in editable property?
        name.connect("edited",self.name_edited_signal)
        view.append_column(gtk.TreeViewColumn('Name',name,text=0))
        mime=gtk.CellRendererText()
        mime.set_property("editable",True)
        mime.connect("edited",self.mime_edited_signal)
        view.append_column(gtk.TreeViewColumn('Mimetype',mime,text=1))
        command=gtk.CellRendererText()
        command.set_property("editable",True)
        command.connect("edited",self.command_edited_signal)
        view.append_column(gtk.TreeViewColumn('Command',command,text=2))

    def init_view(self):
        self.model.clear()
        for mime,tools in settings.custom_launchers.iteritems():
            for tool in tools:
                self.model.append((tool[0],mime,tool[1]))

    def name_edited_signal(self, cellrenderertext, path, new_text):
        print 'name edited',new_text
        name,mime,cmd=self.model[path]
        for i in range(len(settings.custom_launchers[mime])):
            n,c=settings.custom_launchers[mime][i]
            if n==name and c==cmd:
                settings.custom_launchers[mime][i]=(new_text,c)
                break
        self.model[path][0]=new_text

    def mime_edited_signal(self, cellrenderertext, path, new_text):
        name,mime,cmd=self.model[path]
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
        for i in range(len(settings.custom_launchers[mime])):
            n,c=settings.custom_launchers[mime][i]
            if n==name and c==cmd:
                settings.custom_launchers[mime][i]=(n,new_text)
                break
        self.model[path][2]=new_text

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
