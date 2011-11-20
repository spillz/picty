'''
This is a set of simple classes to help create user interaction forms allowing dictionary access
to "named" widgets and a simply mechanism to set and retrieve data values of child widgets
'''

##TODO: Should we add some signal handling helpers (for data valiidation etc)?? (Currently, the caller must set callbacks manually after the construction of the Form object)
##TODO: Form is currently a VBox or HBox, should something else be supported

import gtk

def pack_widgets(parent,container,children):
    parent.widgets={}
    for c in children:
        name=c[0]
        widget=c[1]
        pack_args=c[2:]
        parent.widgets[name]=widget
        container.pack_start(widget,*pack_args)

def gtk_widget(base,setter=None,getter=None):
    class Widget(base):
        def __init__(self,*args):
            base.__init__(self,*args)
            if setter:
                self.set_form_data=setter
            if getter:
                self.get_form_data=getter
        def get_form_data(self):
            return None
        def set_form_data(self,values):
            pass
    return Widget

class Entry(gtk.Entry):
    def __init__(self,default_value=''):
        gtk.Entry.__init__(self)
        if default_value:
            self.set_text(default_value)

    def get_form_data(self):
        return self.get_text()

    def set_form_data(self,values):
        self.set_text(values)


class LabeledEntry(gtk.HBox):
    '''
    A gtk entry plus optional label packed into an HBox
    '''
    def __init__(self,prompt='',default_value=''):
        gtk.HBox.__init__(self,False,8)
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

class Button(gtk.Button):
    def __init__(self,label):
        gtk.Button.__init__(self,label)
    def get_form_data(self):
        return None
    def set_form_data(self,values):
        pass

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

class ComboBox(gtk.ComboBox):
    '''
    A combo box with set of choices
    '''
    def __init__(self,choices,model=None):
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


class ComboBoxEntry(gtk.ComboBoxEntry):
    '''
    A combo box with set of choices
    '''
    def __init__(self,choices,model=None,text_column=-1):
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


class LabeledComboBox(gtk.HBox):
    '''
    A combo box with optional label
    '''
    def __init__(self,label,choices):
        gtk.HBox.__init__(self,False,8)
        if label:
            l=gtk.Label(label)
            self.pack_start(l,False)
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

class HRadioGroup(gtk.HBox,RadioGroup):
    def __init__(self,group_label,labels,*box_args):
        if box_args:
            gtk.HBox.__init__(self,*box_args)
        else:
            gtk.HBox.__init__(self,False,8)
        RadioGroup.__init__(self,group_label,labels)

class VRadioGroup(gtk.VBox,RadioGroup):
    def __init__(self,group_label,labels,*box_args):
        if box_args:
            gtk.VBox.__init__(self,*box_args)
        else:
            gtk.VBox.__init__(self,False,8)
        RadioGroup.__init__(self,group_label,labels)

class LabeledWidgets(gtk.Table):
    '''
    A sequence of widgets embedded in a table. Widgets are laid out in rows with labels.
    The first column displays labels and the second column displays widgets
    '''
    def __init__(self,child_data,spacing=16):
        '''
        Created the LabeledWidgets object
        child_data is a list/tuple
            [
            ('name',widget,'label',xoptions=gtk.EXPAND|gtk.FILL),
            ...
            ]
        '''
        gtk.Table.__init__(self,len(child_data),2)
        self.set_col_spacings(spacing)
        row=0
        self.widgets={}
        for c in child_data:
            label=gtk.Label(c[1])
            label.set_alignment(0,0.5)
            self.attach(label, left_attach=0, right_attach=1, top_attach=row, bottom_attach=row+1,
                   xoptions=gtk.FILL, yoptions=0, xpadding=0, ypadding=0)
            if len(c)>3:
                xopt=c[3] if c[3] else gtk.EXPAND|gtk.FILL
            else:
                xopt=gtk.EXPAND|gtk.FILL
            self.attach(c[2], left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
                   xoptions=xopt, yoptions=0, xpadding=0, ypadding=0) #yoptions=gtk.EXPAND|gtk.FILL
            self.widgets[c[0]]=c[2]
            row+=1

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


class Box:
    '''
    A Form is a container that adds methods to pack a set of standardized
    data entry elements such as Entry, Combo Box, Check Box or even another Box
    '''
    def __init__(self,children):
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
        pack_widgets(self,self,children)

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

class Frame(gtk.Frame):
    def __init__(self,frame_text,child):
        gtk.Frame.__init__(self,frame_text)
        self.add(child)
        self.child=child
    def set_form_data(self,data_dict):
        self.child.set_form_data(data_dict)
    def get_form_data(self):
        return self.child.get_form_data()
    def __getitem__(self,key):
        return self.child[key]

class PaddedVBox(gtk.Alignment,Box):
    def __init__(self,children,*box_args):
        gtk.Alignment.__init__(self,0,0,1,1)
        self.set_padding(16,16,16,16)
        self.box=gtk.VBox(*box_args)
        self.add(self.box)
        pack_widgets(self,self.box,children)

class PaddedHBox(gtk.Alignment,Box):
    def __init__(self,children,*box_args):
        gtk.Alignment.__init__(self,0,0,1,1)
        self.set_padding(16,16,16,16)
        self.box=gtk.HBox(*box_args)
        self.add(self.box)
        pack_widgets(self,self.box,children)

class VBox(gtk.VBox,Box):
    def __init__(self,children,*args):
        gtk.VBox.__init__(self,*args)
        Box.__init__(self,children)

class HBox(gtk.HBox,Box):
    def __init__(self,children,*args):
        gtk.HBox.__init__(self,*args)
        Box.__init__(self,children)

class ModalDialog(gtk.Dialog,Box):
    def __init__(self,children,title=None,buttons=['_Cancel','_OK'],default_button=1):
        '''
        Creates  a gtk.Dialog with the modal flag set and the vbox embedded in an aligment
        to create additional spacing then the widgets in form_spec will be added to the vbox
            butttons is a list/tuple of strings containing the button labels
        '''
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

        pack_widgets(self,self.vbox2,children)
        self.vbox.show_all()



if __name__ == '__main__':

    def quit(window,box):
        print 'DATA',box.get_form_data()
        gtk.main_quit()

    def change_cb(entry):
        print 'Name Changed!'

    def button_cb(button):
        d=ModalDialog([
                    ('lw',LabeledWidgets([
                        ('club','supper club #',Entry()),
                        ('cc','c/c #',Entry()),
                        ]),True,True),
            ],title='Payment Info')
        response=d.run()
        print 'response was',response
        print 'form data'
        print d.get_form_data()
        d.destroy()

    window = gtk.Window()
    b=PaddedVBox([
                ('label',gtk_widget(gtk.Label)('Attendee Preferences')),
                ('name',LabeledEntry('enter your name','sam')),
                ('trees',CheckBox('likes trees?')),
                ('eats',LabeledComboBox('eats',['soup','salad','burgers'])),
                ('drinks',HRadioGroup('drinks',['tea','coffee','water'])),
                ('subbox1',HBox([
                                ('entry2',LabeledEntry('requests','french fries')),
                                ('entry3',LabeledEntry('friends','d')),
                                ],False,8)
                    ),
                ('button1',Button('Payment Info...')),
            ]
            )
    b['name'].entry.connect("changed",change_cb)
    b['button1'].connect("clicked",button_cb)
    window.connect('destroy', quit,b)
    window.add(b)
    window.show_all()
    gtk.main()


