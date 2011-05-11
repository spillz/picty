'''
This is a set of simple classes to help create user interaction forms allowing dictionary access
to "named" widgets and a simply mechanism to set and retrieve data values of child widgets
'''

##TODO: Should we add some signal handling helpers (for data valiidation etc)?? (Currently, the caller must set callbacks manually after the construction of the Form object)
##TODO: Form is currently a VBox or HBox, should something else be supported

import gtk

class Entry(gtk.HBox):
    '''
    A gtk entry plus optional label packed into an HBox
    '''
    def __init__(self,prompt='',default_value=''):
        gtk.HBox.__init__(self)
        if prompt:
            self.label=gtk.Label(prompt)
            self.pack_start(self.label,False)
        self.entry=gtk.Entry()
        self.entry.set_text(default_value)
        self.pack_start(self.entry)
        self.show_all()

    def get_form_data(self):
        return self.entry.get_text()

    def set_form_data(values):
        self.entry.set_text(values)

class CheckBox(gtk.CheckButton):
    '''
    A gtk Check button
    '''
    def __init__(self,label):
        gtk.CheckButton.__init__(self,label)

    def get_form_data(self):
        return self.get_active()

    def set_form_data(self,values):
        self.set_active(values)

class ComboBox(gtk.HBox):
    '''
    A combo box with optional label
    '''
    def __init__(self,label,choices):
        gtk.HBox.__init__(self)
        if label:
            self.pack_start(gtk.Label(label),False)
        self.combo=gtk.combo_box_new_text()
        for c in choices:
            self.combo.append_text(c)
        self.pack_start(self.combo)
        self.show_all()

    def get_form_data(self):
        return self.combo.get_active()

    def set_form_data(self,values):
        self.combo.set_active(values)


class RadioGroup:
    def __init__(self,group_label,labels):
        '''
        labels is a list/tuple of labels for the radio boxes:
        '''
        if group_label:
            self.pack_start(gtk.Label(group_label),False)
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

class HRadioGroup(gtk.HBox,RadioGroup):
    def __init__(self,group_label,labels,*box_args):
        gtk.HBox.__init__(self,*box_args)
        RadioGroup.__init__(self,group_label,labels)

class VRadioGroup(gtk.VBox,RadioGroup):
    def __init__(self,group_label,labels,*box_args):
        gtk.VBox.__init__(self,*box_args)
        RadioGroup.__init__(self,group_label,labels)


class Box:
    '''
    A Form is a container that adds methods to pack a set of standardized
    data entry elements such as Entry, Combo Box, Check Box or even another Box
    '''
    def __init__(self,form_spec):
        '''
        Abstract base for a vbox of hbox with nested widgets as specified in the tuple form_spec
        form_spec is a list or tuple of tuples describing the list of widgets to add:
            [
            ('name1','type1',fill1,expand1,*args1),
            ('name2','type2',fill2,expand2,*args2),
            ...
            ]
            where name is the name of the widget, type is the registered type of the widget, fill, args are the constructor arguments to the widget
        '''
        self.widgets={}
        for f in form_spec:
            print 'creating',f
            name=f[0]
            args=f[2:]
            widget=registered_widgets[f[1]](*args)
            self.widgets[name]=widget
            self.pack_start(widget)

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


class VBox(gtk.VBox,Box):
    def __init__(self,form_spec,*args):
        gtk.VBox.__init__(self,*args)
        Box.__init__(self,form_spec)

class HBox(gtk.HBox,Box):
    def __init__(self,form_spec,*args):
        gtk.HBox.__init__(self,*args)
        Box.__init__(self,form_spec)

##Registered widgets are specified in this dictionary
##A light class wrapper around any gtk widget could be added here provided it has a constructor, set_form_data, get_form_data, (and optionally __getitem__) members
registered_widgets={
'hbox':HBox,
'vbox':VBox,
'entry':Entry,
'hradiogroup':HRadioGroup,
'vradiogroup':VRadioGroup,
'combobox':ComboBox,
'checkbox':CheckBox,
}

def quit(window,box):
    print 'DATA',box.get_form_data()
    gtk.main_quit()

def change_cb(entry):
    print 'Name Changed!'

if __name__ == '__main__':
    window = gtk.Window()
    b=VBox([
                ('entry1','entry','enter your name','sam'),
                ('checkbox1','checkbox','likes trees?'),
                ('combobox1','combobox','eats',['soup','salad','burgers']),
                ('radiogroup1','hradiogroup','drinks',['tea','coffee','water']),
                ('subbox1','hbox',
                    [
                        ('entry1','entry','requests','french fries'),
                        ('entry2','entry','friends','d'),
                    ]),
            ]
            )
    b['entry1'].entry.connect("changed",change_cb)
    window.connect('destroy', quit,b)
    window.add(b)
    window.show_all()
    gtk.main()
