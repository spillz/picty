import gtk

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
