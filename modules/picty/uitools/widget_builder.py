'''
This is a set of simple widgets that subclass existing gtk widgets to make the creation of user interaction
forms simpler. There are 3 main features:
    1. Simpler constructors that make it simpler to nest child widgets into container widgets or initialize data models
    2. Dictionary access to child widget via "named" widgets of the root container widget
    3. A simply mechanism to set and retrieve data values of child widgets using get_form_data and set_form_data

A few classes combine multiple widgets together:
    LabeledEntry
    LabeledComboBox
    LabeledWidgets

See the if __name__ == '__main__' block for examples.

'''

##TODO: Should we add some signal handling helpers (for data valiidation etc)?? (Currently, the caller must set callbacks manually after the construction of the Form object)
##TODO: Form is currently a VBox or HBox, should something else be supported?

import gtk

class GlobalNode:
    def __init__(self):
        self.data = set()
    def add_it(self, obj):
        self.data.add(obj)

parent_node = GlobalNode()

class Pack:
    '''
    Used under a with statement to pack a gtk object into a widget_builder container
    For example:

    with VBox():
        Pack(Gtk.Label('test'))
    '''
    def __init__(self, obj, *pack_args):
        global parent_node
        parent_node.add_it(obj, *pack_args)


class Packer:
    '''
    A context for widget_builder objects (all widget_builder objects are subclassed from Packer)
    Allows for packing of widgets into containers by nesting
    widget_builder object declarations under a with block
    '''
    def __init__(self, *pack_args):
        global parent_node
        parent_node.add_it(self, *pack_args)

    def __enter__(self):
        global parent_node
        self.orig_parent = parent_node
        parent_node = self

    def __exit__(self, type, value, traceback):
        global parent_node
        parent_node = self.orig_parent

def pack_widgets(parent,container,children):
    '''
    used to pack widgets into a box using pack_start
    children is a iterable of tuples that are of the form (string_id, widget, pack_args) or (widget, pack_args)
    if there is no string_id, the widget will not be added to the dictionary and it's data won't be extracted with
    the call to get_form_data. It's useful for adding regular gtk widgets that don't have children and data is not
    required (e.g. a label).
    '''
    parent.widgets={}
    for c in children:
        if type(c[0]) == str:
            name=c[0]
            widget=c[1]
            pack_args=c[2:]
            parent.widgets[name]=widget
        else:
            widget = c[0]
            pack_args = c[1:]
        container.pack_start(widget,*pack_args)

def pack_widget(parent, container, widget, pack_args):
    '''
    used to pack widgets into a box using pack_start
    children is a iterable of tuples that are of the form (string_id, widget, pack_args) or (widget, pack_args)
    if there is no string_id, the widget will not be added to the dictionary and it's data won't be extracted with
    the call to get_form_data. It's useful for adding regular gtk widgets that don't have children and data is not
    required (e.g. a label).
    '''
    if len(pack_args)>0 and type(pack_args[0]) == str:
        name = pack_args[0]
        pack_args= pack_args[1:]
        parent.widgets[name] = widget
    print 'packing',parent,container,widget
    container.pack_start(widget,*pack_args)

def gtk_widget(base,setter=None,getter=None):
    '''
    use this wrapper to add a GTK widget in places where a widget_builder widget is expected
    '''
    class Widget(base, Pack):
        def __init__(self, pack_args = (), *args):
            base.__init__(self,*args)
            Pack.__init__(self, self, *pack_args)
            if setter:
                self.set_form_data=setter
            if getter:
                self.get_form_data=getter
        def get_form_data(self):
            return None
        def set_form_data(self,values):
            pass
    return Widget

class Entry(gtk.Entry, Packer):
    def __init__(self,default_value='', pack_args = ()):
        gtk.Entry.__init__(self)
        Packer.__init__(self, *pack_args)
        if default_value:
            self.set_text(default_value)

    def get_form_data(self):
        return self.get_text()

    def set_form_data(self,values):
        self.set_text(values)

class TextView(gtk.TextView, Packer):
    def __init__(self,default_value='', pack_args = ()):
        gtk.TextView.__init__(self)
        Packer.__init__(self, *pack_args)
        if default_value:
            self.get_buffer().set_text(default_value)

    def get_form_data(self):
        return self.get_buffer().get_text()

    def set_form_data(self,values):
        self.get_buffer().set_text(values)

class ScrollingTextView(gtk.ScrolledWindow, Packer):
    def __init__(self,default_value='', pack_args = ()):
        gtk.ScrolledWindow.__init__(self)
        Packer.__init__(self, *pack_args)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.text_view = gtk.TextView()
        self.add(self.text_view)
        if default_value:
            self.text_view.get_buffer().set_text(default_value)

    def get_form_data(self):
        return self.text_view.get_buffer().get_text(*self.text_view.get_buffer().get_bounds())

    def set_form_data(self,values):
        self.text_view.get_buffer().set_text(values)


class LabeledEntry(gtk.HBox, Packer):
    '''
    A gtk entry plus optional label packed into an HBox
    '''
    def __init__(self,prompt='',default_value='', pack_args = ()):
        gtk.HBox.__init__(self,False,8)
        Packer.__init__(self, *pack_args)
        if prompt:
            l=gtk.Label(prompt)
            self.pack_start(l,False)
        self.entry=gtk.Entry()
        self.entry.set_text(default_value)
        self.pack_start(self.entry)
        self.show_all()

    def get_form_data(self):
        return self.entry.get_text()

    def set_form_data(self,values):
        self.entry.set_text(values)

class Button(gtk.Button, Packer):
    def __init__(self,label, pack_args = ()):
        gtk.Button.__init__(self,label)
        Packer.__init__(self, *pack_args)
    def get_form_data(self):
        return None
    def set_form_data(self,values):
        pass

class CheckBox(gtk.CheckButton, Packer):
    '''
    A gtk Check button
    '''
    def __init__(self,label, pack_args = ()):
        gtk.CheckButton.__init__(self,label)
        Packer.__init__(self, *pack_args)

    def get_form_data(self):
        return self.get_active()

    def set_form_data(self,values):
        self.set_active(values)

class ComboBox(gtk.ComboBox, Packer):
    '''
    A combo box with set of choices
    '''
    def __init__(self,choices,model=None, pack_args = ()):
        '''
        creates a new combo box
        choices is a list or tuple of combobox rows
        if model==None, the combo box is set up with a Text Cell Render and a model with a single column
        of type str
        otherwise, model should be a liststore, with choices containing a list of tuples dimensioned
        appropriately and the caller must add appropriate cell renderers
        '''
        if model==None:
            liststore = gtk.ListStore(str)
        else:
            liststore=model

        gtk.ComboBox.__init__(self,liststore)
        Packer.__init__(self, *pack_args)
        if model==None:
            cell = gtk.CellRendererText()
            self.pack_start(cell, True)
            self.add_attribute(cell, 'text', 0)

        for c in choices:
            if type(c)==str:
                liststore.append([c])
            else:
                liststore.append(c)

    def get_form_data(self):
        return self.get_active()

    def set_form_data(self,values):
        self.set_active(values)


class ComboBoxEntry(gtk.ComboBoxEntry, Packer):
    '''
    A combo box with set of choices
    '''
    def __init__(self,choices,model=None,text_column=-1, pack_args = ()):
        '''
        creates a new combo box
        choices is a list or tuple of combobox rows
        if model==None, the combo box is set up with a Text Cell Render and a model with a single column
        of type str
        otherwise, model should be a liststore, with choices containing a list of tuples dimensioned
        appropriately and the caller must add appropriate cell renderers
        '''
        if model==None:
            liststore = gtk.ListStore(str)
        else:
            liststore=model

        gtk.ComboBoxEntry.__init__(self,liststore,text_column)
        Packer.__init__(self, *pack_args)
        if model==None:
            cell = gtk.CellRendererText()
            self.pack_start(cell, True)
            self.add_attribute(cell, 'text', 0)

        for c in choices:
            if type(c)==str:
                liststore.append([c])
            else:
                liststore.append(c)

    def get_form_data(self):
        return self.get_active(),self.child.get_text()

    def set_form_data(self,values):
        self.child.set_text(values[1])
        self.set_active(values[0])


class LabeledComboBox(gtk.HBox, Packer):
    '''
    A combo box with optional label
    '''
    def __init__(self,label,choices,model=None, pack_args = ()):
        gtk.HBox.__init__(self,False,8)
        Packer.__init__(self, *pack_args)
        if label:
            l=gtk.Label(label)
            self.pack_start(l,False)
        self.combo=gtk.ComboBox(model)
        if model==None:
            model=gtk.ListStore(str)
            cell = gtk.CellRendererText()
            self.combo.pack_start(cell, True)
            self.combo.add_attribute(cell, 'text', 0)
            self.combo.set_model(model)
        for c in choices:
            if type(c)==str:
                model.append([c])
            else:
                model.append(c)
        self.pack_start(self.combo)
        self.show_all()

    def get_form_data(self):
        return self.combo.get_active()

    def set_form_data(self,values):
        self.combo.set_active(values)


class RadioGroup(Packer):
    def __init__(self,group_label,labels, pack_args = ()):
        '''
        labels is a list/tuple of labels for the radio boxes:
        '''
        Packer.__init__(self, *pack_args)
        if group_label:
            l=gtk.Label(group_label)
            self.pack_start(l,False)
        self.items=[]
        grp=gtk.RadioButton(None,labels[0],True)
        self.pack_start(grp)
        self.items.append(grp)
        for o in labels[1:]:
            i=gtk.RadioButton(grp,o,True)
            self.items.append(i)
            self.pack_start(i)
        self.show_all()

    def get_form_data(self):
        for i in range(len(self.items)):
            if self.items[i].get_active():
                return i
        return -1


    def set_form_data(self,values):
        self.items[0].set_property("current-value",values)

class HRadioGroup(gtk.HBox, RadioGroup):
    def __init__(self,group_label,labels, box_args = (), pack_args = ()):
        if box_args:
            gtk.HBox.__init__(self,*box_args)
        else:
            gtk.HBox.__init__(self,False,8)
        RadioGroup.__init__(self,group_label,labels, pack_args)

class VRadioGroup(gtk.VBox,RadioGroup):
    def __init__(self,group_label,labels, box_args = (), pack_args = ()):
        if box_args:
            gtk.VBox.__init__(self,*box_args)
        else:
            gtk.VBox.__init__(self,False,8)
        RadioGroup.__init__(self,group_label,labels, pack_args)

class LabeledWidgets(gtk.Table, Packer):
    '''
    A sequence of widgets embedded in a table. Widgets are laid out in rows with labels.
    The first column displays labels and the second column displays widgets
    '''
    def __init__(self, rows, spacing=16, pack_args = ()):
        '''
        Created the LabeledWidgets object
        child_data is a list/tuple
            [
            ('name',widget,'label',xoptions=gtk.EXPAND|gtk.FILL),
            ...
            ]
        '''
        gtk.Table.__init__(self, rows, 2)
        Packer.__init__(self, *pack_args)
        self.set_col_spacings(spacing)
        self.row=0
        self.widgets={}

    def add_it(self, obj, *pack_data):
        try:
            name, label, xopt = pack_data
        except:
            name, label = pack_data
            xopt = gtk.EXPAND|gtk.FILL
        label=gtk.Label(label)
        label.set_alignment(0,0.5)
        self.attach(label, left_attach=0, right_attach=1, top_attach=self.row, bottom_attach=self.row+1,
               xoptions=gtk.FILL, yoptions=0, xpadding=0, ypadding=0)
        self.attach(obj, left_attach=1, right_attach=2, top_attach=self.row, bottom_attach=self.row+1,
               xoptions=xopt, yoptions=0, xpadding=0, ypadding=0) #yoptions=gtk.EXPAND|gtk.FILL
        self.widgets[name]=obj
        self.row+=1

    def __getitem__(self,key):
        return self.widgets[key]

    def set_form_data(self,data_dict):
        for k in data_dict:
            self.widgets[k].set_form_data(data_dict[k])

    def get_form_data(self):
        data={}
        for k in self.widgets:
            data[k]=self.widgets[k].get_form_data()
        return data


class Notebook(gtk.Notebook, Packer):
    def __init__(self, pack_args = ()):
        '''
        `child_pages` is a list of tuples of the form (identifier, page label, page widget)
        '''
        gtk.Notebook.__init__(self)
        Packer.__init__(self, *pack_args)
        self.widgets={}

    def add_it(self, obj, *pack_args):
        ident, label = pack_args
        if isinstance(label,str):
            label=gtk.Label(label)
        self.append_page(obj,label)
        self.widgets[ident]=obj

    def __getitem__(self,key):
        return self.widgets[key]

    def set_form_data(self,data_dict):
        for k in data_dict:
            self.widgets[k].set_form_data(data_dict[k])

    def get_form_data(self):
        data={}
        for k in self.widgets:
            data[k]=self.widgets[k].get_form_data()
        return data


class Box(Packer):
    '''
    A Box is a container that adds methods to pack a set of standardized
    data entry elements such as Entry, Combo Box, Check Box or even another Box
    '''
    def __init__(self, container, pack_args = ()):
        '''
        Abstract base for a vbox of hbox with nested widgets as specified in the tuple form_spec
        children is a list or tuple of tuples describing the list of widgets to add:
            [
            ('name1',obj1,*pack_args1),
            ('name2',obj2,*pack_args2),
            ...
            ]
            where name is the name of the widget, obj is a widget builder instance, args are the packing arguments
        '''
        self.container = container
        self.widgets={}
        Packer.__init__(self, *pack_args)
#        pack_widgets(self,self,children)

    def __getitem__(self,key):
        return self.widgets[key]

    def add_it(self, obj, *pack_args):
        pack_widget(self, self.container, obj, pack_args)

    def set_form_data(self,data_dict):
        for k in data_dict:
            self.widgets[k].set_form_data(data_dict[k])

    def get_form_data(self):
        data={}
        for k in self.widgets:
            data[k]=self.widgets[k].get_form_data()
        return data

class Frame(gtk.Frame, Packer):
    def __init__(self, frame_text, pack_args = ()):
        gtk.Frame.__init__(self,frame_text)
        Packer.__init__(self, *pack_args)
        self.child = None

    def add_it(self, child, *args):
        self.add(child)
        self.child=child

    def set_form_data(self,data_dict):
        self.child.set_form_data(data_dict)

    def get_form_data(self):
        return self.child.get_form_data()

    def __getitem__(self,key):
        return self.child[key]

class PaddedVBox(gtk.Alignment,Box):
    def __init__(self, box_args = (), pack_args = ()):
        gtk.Alignment.__init__(self,0,0,1,1)
        self.set_padding(16,16,16,16)
        self.box=gtk.VBox(*box_args)
        self.add(self.box)
        Box.__init__(self, self.box, pack_args)

class PaddedHBox(gtk.Alignment,Box):
    def __init__(self, box_args = (), pack_args = ()):
        gtk.Alignment.__init__(self,0,0,1,1)
        self.set_padding(16,16,16,16)
        self.box=gtk.HBox(*box_args)
        self.add(self.box)
        Box.__init__(self, self.box, pack_args)

class VBox(gtk.VBox,Box):
    def __init__(self, box_args = (), pack_args = ()):
        gtk.VBox.__init__(self,*box_args)
        Box.__init__(self, self, pack_args)

class HBox(gtk.HBox,Box):
    def __init__(self, box_args = (), pack_args = ()):
        gtk.HBox.__init__(self, *box_args)
        Box.__init__(self, self, pack_args)

class ModalDialog(gtk.Dialog,Box, Packer):
    def __init__(self,title=None,buttons=['_Cancel','_OK'],default_button=1, pack_args = ()):
        '''
        Creates  a gtk.Dialog with the modal flag set and the vbox embedded in an aligment
        to create additional spacing then the widgets in form_spec will be added to the vbox
            butttons is a list/tuple of strings containing the button labels
        '''
        Packer.__init__(self, *pack_args)
        i=0
        button_list=[]
        for x in buttons:
            button_list.append(x)
            button_list.append(i)
            i+=1
        gtk.Dialog.__init__(self,title=title,flags=gtk.DIALOG_NO_SEPARATOR|gtk.DIALOG_MODAL,buttons=tuple(button_list))
        self.set_default_response(default_button)
        vbox=gtk.VBox()
        a=gtk.Alignment(0,0,1,1)
        a.set_padding(16,16,16,16)
        self.vbox.pack_start(a,True,True)
        a.add(vbox)
        self.vbox2=vbox
        self.vbox.show_all()
        self.widgets = {}

    def add_it(self, obj, *pack_args):
        pack_widget(self, self.vbox2, obj, pack_args)
    ##TODO: overload __exit__ to do a self.vbox.show_all()??


if __name__ == '__main__':

    def quit(window,box):
        print 'DATA',box.get_form_data()
        gtk.main_quit()

    def change_cb(entry):
        print 'Name Changed!'

    def button_cb(button):
        d = ModalDialog(title = 'Payment Info')
        with d:
            with LabeledWidgets(rows = 2, pack_args = ('lw',True, True)):
                Entry(pack_args = ('club', 'supper club #'))
                Entry(pack_args = ('cc', 'c/c #'))
        d.show_all()
        response=d.run()
        print 'response was',response
        print 'form data'
        print d.get_form_data()
        d.destroy()

    window = gtk.Window()
    b=PaddedVBox(box_args = (False, 8))
    with b:
        Pack(gtk.Label('Attendee Preferences'))
        LabeledEntry('name','sam', pack_args = ('name',))
        CheckBox('likes trees?', pack_args = ('trees',))
        LabeledComboBox('eats',['soup','salad','burgers'], pack_args = ('eats',))
        HRadioGroup('drinks',['tea','coffee','water'], pack_args = ('drinks',))
        with HBox(box_args = (False, 8), pack_args = ('subbox1',)):
            LabeledEntry('requests','french fries', pack_args = ('entry1',))
            LabeledEntry('friends','d', pack_args = ('entry2',))
        Button('Payment Info...', pack_args = ('button1',)),
    b['name'].entry.connect("changed",change_cb)
    b['button1'].connect("clicked",button_cb)
    window.connect('destroy', quit,b)
    window.add(b)
    window.show_all()
    print b.get_form_data()
    gtk.main()
