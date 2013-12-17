import gtk
import gobject
import overlay_tools

#Custom toolbutton, toolitem and toolbar (makes it easier to plugins to add remove their own items for picty toolbars)
class ToolButton(gtk.ToolButton):
    def __init__(self,label,callback,update_cb,icons,owner='Main',tooltip=None,priority=50,expand=False,):
        gtk.ToolButton.__init__(self,icons[0])
        self.icons = icons
        self.owner = owner
        self.priority = priority
        self.update_cb = update_cb
        if isinstance(callback,tuple):
            self.connect("clicked",callback[0],*callback[1:])
        else:
            self.connect("clicked",callback)
        if tooltip:
            self.set_tooltip_text(tooltip)
        if label:
            self.set_label(label)
        self.set_expand(expand)


class ToggleToolButton(gtk.ToggleToolButton):
    def __init__(self,label,callback,update_cb,icons,owner='Main',tooltip=None,priority=50,expand=False,):
        gtk.ToggleToolButton.__init__(self,icons[0])
        self.icons = icons
        self.owner = owner
        self.priority = priority
        self.update_cb = update_cb
        if isinstance(callback,tuple):
            self.connect("clicked",callback[0],*callback[1:])
        else:
            self.connect("clicked",callback)
        if tooltip:
            self.set_tooltip_text(tooltip)
        if label:
            self.set_label(label)
        self.set_expand(expand)


class ToolItem(gtk.ToolItem):
    def __init__(self,widget,owner='Main',update_cb=None,priority=50,expand=False):
        gtk.ToolItem.__init__(self)
        self.add(widget)
        self.owner = owner
        self.update_cb=update_cb
        self.priority = priority
        self.set_expand(expand)

class Toolbar(gtk.Toolbar):
    def __init__(self):
        gtk.Toolbar.__init__(self)
        overlay_tools.overlay_groups.append(self)

    ##TODO: make these callbacks part of a derived class for the viewer
    def default_update_callback(self,tool,viewer):
        return self.cb_has_item(tool,viewer)

    def cb_has_item(self, tool, viewer):
        if viewer.item!=None:
            tool.set_sensitive(True)
        else:
            tool.set_sensitive(False)
    def cb_has_image(self, tool, viewer):
        if viewer.item!=None and 'qview' in viewer.item.__dict__ and viewer.item.qview is not None:
            tool.set_sensitive(True)
        else:
            tool.set_sensitive(False)
    def cb_showing_tranforms(self, tool, viewer):
        if viewer.item!=None:
            if 'ImageTransforms' in viewer.item.meta and viewer.il.want_transforms:
                tool.set_sensitive(True)
                return
            if 'ImageTransforms' not in viewer.item.meta:
                tool.set_sensitive(True)
                return
        tool.set_sensitive(False)
    def cb_has_image_edits(self, tool, viewer):
        if viewer.item!=None and 'ImageTransforms' in viewer.item.meta:
            tool.set_sensitive(True)
        else:
            tool.set_sensitive(False)
    def cb_item_changed(self, tool, viewer):
        if viewer.item!=None and viewer.item.is_meta_changed():
            tool.set_sensitive(True)
        else:
            tool.set_sensitive(False)
    def cb_item_changed_icon(self, tool, viewer):
        if viewer.item!=None and viewer.item.is_meta_changed():
            tool.set_sensitive(True)
            if viewer.item.is_meta_changed()==2:
                tool.set_stock_id(tool.icons[1])
            else:
                tool.set_stock_id(tool.icons[0])
        else:
            tool.set_sensitive(False)
            tool.set_stock_id(tool.icons[0])
    def cb_item_not_deleted(self,tool, viewer):
        if viewer.item!=None and viewer.item.is_meta_changed()!=2:
            tool.set_sensitive(True)
        else:
            tool.set_sensitive(False)

    def register_tool(self,name,action_callback=None,update_callback=overlay_tools.show_on_hover,icons=[],owner='Main',tooltip='This is a tooltip',priority=50,toggle=False):
        if toggle:
            new_t=ToggleToolButton(name,action_callback,update_callback,icons,owner,tooltip,priority)
        else:
            new_t=ToolButton(name,action_callback,update_callback,icons,owner,tooltip,priority)
        for i in range(self.get_n_items()):
            t = self.get_nth_item(i)
            if type(t) in (ToolButton, ToggleToolButton):
                if priority>t.priority:
                    self.insert(new_t,i)
                    return
        self.add(new_t)

    def register_tool_for_plugin(self,plugin,name,action_callback=None,update_callback=overlay_tools.show_on_hover,icons=None,tooltip='This is a tooltip',priority=50):
        '''
        adds a new tool whose owner is plugin
        '''
        self.register_tool(name,action_callback,update_callback,icons,plugin.name,tooltip,priority)

    def deregister_tools_for_plugin(self,plugin):
        '''
        removes all tools whose owners are plugin
        '''
        tools=[self.get_nth_item(i) for i in range(self.get_n_items()) if type(self.get_nth_item(i))==ToolButton and self.get_nth_item(i).owner==plugin.name]
        for t in tools:
            self.remove(t)

    def update_status(self,*args):
        tools=[self.get_nth_item(i) for i in range(self.get_n_items()) if type(self.get_nth_item(i)) in (ToolButton,ToolItem)]
        for t in tools:
            if t.update_cb is not None:
                t.update_cb(t,*args)

##shortcuts for adding items to a toolbar
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
