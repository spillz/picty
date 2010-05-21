import gtk
import widget_tools


class FloatingPanel(gtk.Dialog):
    def __init__(self,title):
        gtk.Dialog.__init__(self,title)
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
        self.toggle.set_active(False)
        return True


class FloatingPanelManager:
    def __init__(self,mainframe):
        self.panels={}
        self.mainframe=mainframe
    def add_panel(self,title,tooltip_text,icon_name):
        p=FloatingPanel(title)
        p.toggle=gtk.ToggleToolButton(icon_name)
        p.toggle.show()
        self.panels[title]=p
        widget_tools.add_item(self.mainframe.toolbar1,p.toggle,p.toggle_panel,title,tooltip_text)
        return p
    def remove_panel(self,title):
        p=self.panels[title]
        if p.toggle!=None:
            self.mainframe.toolbar1.remove(p.toggle)
        p.toggle.destroy()
        p.destroy()
        del self.panels[title]
