import gtk
import gobject
import overlaytools

##shortcuts for adding items to a toolbar
class ToolButton(gtk.ToolButton):
    def __init__(self,label,callback,state_cb,icons,owner='Main',tooltip=None,priority=50,expand=False,):
       ##'Zoom In',self.zoom_item_in,show_on_hover,[gtk.STOCK_ZOOM_IN],'Main','Zoom in')
        gtk.ToolButton.__init__(self,icons[0])
        self.icons = icons
        self.owner = owner
        self.priority = priority
        self.state_cb = state_cb
        if callback:
            self.connect("clicked",callback)
        if tooltip:
            self.set_tooltip_text(tooltip)
        if label:
            self.set_label(label)
        self.set_expand(expand)

gobject.type_register(ToolButton)

class Toolbar(gtk.Toolbar):
    def __init__(self):
        gtk.Toolbar.__init__(self)
        overlaytools.overlay_groups.append(self)

    def default_active_callback(self,item,hover):
        return int(hover)-1

    def register_tool(self,name,action_callback=None,active_callback=overlaytools.show_on_hover,icons=[],owner='Main',tooltip='This is a tooltip',priority=50):
        new_t=ToolButton(name,action_callback,active_callback,icons,owner,tooltip,priority)
        for i in range(self.get_n_items()):
            t = self.get_nth_item(i)
            if type(t)==ToolButton:
                if priority>t.priority:
                    self.insert(new_t,i)
                    return
        self.add(new_t)

    def register_tool_for_plugin(self,plugin,name,action_callback=None,active_callback=overlaytools.show_on_hover,icons=None,tooltip='This is a tooltip',priority=50):
        '''
        adds a new tool whose owner is plugin
        '''
        self.register_tool(name,action_callback,active_callback,icons,plugin.name,tooltip,priority)

    def deregister_tools_for_plugin(self,plugin):
        '''
        removes all tools whose owners are plugin
        '''
        tools=[self.get_nth_item(i) for i in range(self.get_n_items()) if type(self.get_nth_item(i))==ToolButton and self.get_nth_item(i).owner==plugin.name]
        for t in tools:
            self.remove(t)



def add_item(toolbar,widget,callback,label=None,tooltip=None,expand=False):
    toolbar.add(widget)
    if callback:
        widget.connect("clicked", callback)
    if tooltip:
        widget.set_tooltip_text(tooltip)
    if label:
        widget.set_label(label)
    if expand:
        widget.set_expand(True)

def add_widget(toolbar,widget,callback,label=None,tooltip=None,expand=False):
    item=gtk.ToolItem()
    item.add(widget)
    toolbar.add(item)
    if callback:
        widget.connect("clicked", callback)
    if tooltip:
        widget.set_tooltip_text(tooltip)
    if label:
        item.set_label(label)
    if expand:
        item.set_expand(True)

def set_item(widget,callback,label,tooltip):
    if callback:
        widget.connect("clicked", callback)
    if tooltip:
        widget.set_tooltip_text(tooltip)
    if label:
        widget.set_label(label)
    return widget

def add_frame(toolbar,label,items,expand=False):
    item=gtk.ToolItem()
    frame=gtk.Frame(label)
    box=gtk.HBox()
    item.add(frame)
    frame.add(box)
    for i in items:
        if len(i)==5:
            box.pack_start(set_item(*i[:4]),i[4])
        else:
            box.pack_start(set_item(*i))
    toolbar.add(item)
    if expand:
        item.set_expand(True)
