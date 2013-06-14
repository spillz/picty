import gtk
import widget_tools


class FloatingPanel(gtk.Dialog):
    def __init__(self,title):
        gtk.Dialog.__init__(self,title)
        self.set_default_size(300,400)
        self.set_title(title)
#        self.set_deletable(False)
        self.connect("delete-event",self.close_button_cb)
        self.toggle=None
    def toggle_panel(self,widget):
        if widget.get_active():
            self.show()
        else:
            self.hide()
    def close_button_cb(self,widget,event):
        if self.toggle:
            self.toggle.set_active(False)
        return True

class FloatingWindow(gtk.Window):
    def __init__(self,title):
        gtk.Window.__init__(self)
        self.set_default_size(300,400)
#        self.set_deletable(False)
        self.connect("delete-event",self.close_button_cb)
        self.toggle=None
    def toggle_panel(self,widget):
        if widget.get_active():
            self.show()
        else:
            self.hide()
    def close_button_cb(self,widget,event):
        if self.toggle:
            self.toggle.set_active(False)
        return True


class FloatingPanelManager:
    def __init__(self,mainframe):
        self.panels={}
        self.mainframe=mainframe
    def add_panel(self,title,tooltip_text=None,icon_name=None,panel=True,add_to_toolbar=True):
        if panel:
            p=FloatingPanel(title)
        else:
            p=FloatingWindow(title)
        p.set_transient_for(self.mainframe.window)
        p.set_destroy_with_parent(True)
        self.panels[title]=p
        if icon_name:
            p.toggle=gtk.ToggleToolButton(icon_name)
            p.toggle.show()
            if add_to_toolbar:
                widget_tools.add_item(self.mainframe.toolbar1,p.toggle,p.toggle_panel,title,tooltip_text)
        return p
    def remove_panel(self,title):
        p=self.panels[title]
        if p.toggle!=None:
            self.mainframe.toolbar1.remove(p.toggle)
        p.toggle.destroy()
        p.destroy()
        del self.panels[title]
