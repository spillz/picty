import gtk

class ContextMenu():
    '''
    an implementation of a context menu that makes it easy for plugins
    to add/remove items
    TODO: need an add_submenu
    '''
    def __init__(self):
        self.menu = gtk.Menu()
        self.items = []

    def _add_item(self,item,priority=None):
        i=0
        while priority is not None and i < len(self.items):
            if priority<self.items[i].priority:
                self.menu.insert(item,i)
                self.items.insert(i,item)
                break
            i+=1
        if priority is None or i == len(self.items):
            item.priority = self.items[-1].priority - 10 if len(self.items)>0 else 1000
            self.menu.append(item)
            self.items.append(item)

    def add_menu(self,text,sub_menu,owner=None, priority=None):
        item=gtk.MenuItem(text)
        sub_menu.menu.show()
        item.set_submenu(sub_menu.menu)
        item.owner=owner
        item.show_callback = None
        self._add_item(item,priority)

    def add_separator(self,owner=None, priority=None):
        item = gtk.SeparatorMenuItem()
        item.owner = owner
        item.show_callback = None
        self._add_item(item,priority)

    def add(self,text,callback,show_callback=None,owner=None,priority=None,args=tuple()):
        item = gtk.MenuItem(text)
        item.connect("activate",callback,*args)
        item.owner=owner
        item.show()
        item.show_callback = show_callback
        self._add_item(item,priority)

    def remove_by_owner(self,owner=None):
        i=0
        while i<len(self.items):
            if self.items[i].owner == owner:
                self.menu.remove(self.items[i])
                del self.items[i]
            else:
                i+=1
    def popup(self):
        for item in self.items:
            if item.show_callback is None or item.show_callback(item):
                item.show()
            else:
                item.hide()
        self.menu.show()
        self.menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)

if __name__ == '__main__':
    #a simple test of the context menu class
    def f(item):
        '''context menu callback'''
        #todo: put in some assertions
        print item
        print item.get_label()
        print item.owner
        print menu.items
        menu.remove_by_owner()
        print menu.items
        gtk.main_quit()

    menu = ContextMenu()
    menu.add("option 1",f)
    menu.add("option 2",f)
    menu.add_separator()

    submenu = ContextMenu()
    submenu.add("suboption1",f)
    submenu.add("suboption2",f)
    menu.add_menu("sub menu",submenu)

    win = gtk.Window(gtk.WINDOW_TOPLEVEL)
    but = gtk.Button("click for menu")
    but.connect("clicked",lambda b:menu.popup())
    win.add(but)
    win.show_all()
    gtk.main()
