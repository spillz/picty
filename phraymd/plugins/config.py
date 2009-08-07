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
