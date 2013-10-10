import gtk
import widget_tools


class FloaterBase:
    '''
    provides common functionality for floating windows provided by the app (e.g. the fullscreen window, the map window etc)
    '''
    def move_to_other_monitor(self,ref_window=None,is_fullscreen=False):
        if ref_window is not None:
            screen = ref_window.get_screen()
            (xs,ys) = ref_window.get_position()
        else:
            screen = self.get_screen()
            (xs,ys) = self.get_position()
        (x,y) = self.get_position()
        num_mons = screen.get_n_monitors()
        if num_mons<=1:
            return
        mon_old = screen.get_monitor_at_point(xs,ys)
        mon_curr = screen.get_monitor_at_point(x,y)
        if mon_old!=mon_curr:
            return
        if is_fullscreen:
            self.unfullscreen()
        mon_new = num_mons-mon_old-1
        old_rect = screen.get_monitor_geometry(mon_old)
        new_rect = screen.get_monitor_geometry(mon_new)
        new_x = (x - old_rect.x) + new_rect.x
        new_x = min(new_x,new_rect.x+3*new_rect.width/4)
        new_y = (y - old_rect.y) + new_rect.y
        new_y = min(new_y,new_rect.y+3*new_rect.height/4)
        self.move(new_x,new_y)
        if is_fullscreen:
            self.fullscreen()
    def toggle_panel(self,widget):
        if widget.get_active():
            self.show()
        else:
            self.hide()
    def close_button_cb(self,widget,event):
        if self.toggle:
            self.toggle.set_active(False)
        return True



class FloatingPanel(gtk.Dialog,FloaterBase):
    def __init__(self,title):
        gtk.Dialog.__init__(self,title)
        self.set_default_size(300,400)
        self.set_title(title)
#        self.set_deletable(False)
        self.connect("delete-event",self.close_button_cb)
        self.toggle=None

class FloatingWindow(gtk.Window,FloaterBase):
    def __init__(self,title):
        gtk.Window.__init__(self)
        self.set_default_size(300,400)
#        self.set_deletable(False)
        self.connect("delete-event",self.close_button_cb)
        self.toggle=None


class FloatingPanelManager:
    def __init__(self,mainframe):
        self.panels={}
        self.mainframe=mainframe
    def add_panel(self,title,tooltip_text=None,icon_name=None,panel=True,add_to_toolbar=True,use_other_monitor=True):
        if panel:
            p=FloatingPanel(title)
        else:
            p=FloatingWindow(title)
        p.set_transient_for(self.mainframe.window)
        p.set_destroy_with_parent(True)
        if use_other_monitor:
            p.move_to_other_monitor()
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
