'''

    phraymd
    Copyright (C) 2013  Damien Moore

License:

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

##todo: rename this module commonui

import os
import gtk

from datetime import date

#local imports
import settings
import metadata
import io
import baseobjects

def box_add(box,widget_data,label_text):
    hbox=gtk.HBox()
    if label_text:
        label=gtk.Label(label_text)
        hbox.pack_start(label,False)
    for widget in widget_data:
        hbox.pack_start(widget[0],widget[1])
        if widget[2]:
            widget[0].connect(widget[2],widget[3])
    box.pack_start(hbox,False)
    return tuple([hbox]+[widget[0] for widget in widget_data])


class PathnameCombo(gtk.VBox):
    def __init__(self,default_path,label,browse_prompt,volume_monitor=None,directory=True):
        gtk.VBox.__init__(self)
        self.browse_prompt=browse_prompt
        self.directory=directory
        self.model=gtk.ListStore(str,gtk.gdk.Pixbuf,str)
        self.vm=volume_monitor
        volume_monitor.connect_after("mount-added",self.set_mounts)
        volume_monitor.connect_after("mount-removed",self.set_mounts)
        self.combo_entry=gtk.ComboBoxEntry(self.model,0)
        cpb=gtk.CellRendererPixbuf()
        self.combo_entry.pack_start(cpb,False)
        self.combo_entry.reorder(cpb, 0)
        self.combo_entry.add_attribute(cpb, 'pixbuf', 1)

        box,self.path_entry,self.browse_dir_button=box_add(self,
            [(self.combo_entry,True,None),
            (gtk.Button('...'),False,"clicked",self.browse_path)], #stock=gtk.STOCK_OPEN
            label)
        self.set_mounts()
    def set_mounts(self,*args):
        iter=self.combo_entry.get_active_iter()
        if iter:
            last_active=list(self.model[iter])
        else:
            last_active=None
        self.model.clear()
        t=gtk.icon_theme_get_default()
        mi=self.vm.get_mount_info()
        for name,icon_names,path in mi:
            ii=t.choose_icon(icon_names,gtk.ICON_SIZE_MENU,0)
            pb=None if not ii else ii.load_icon()
            iter=self.model.append((name,pb,path))
            if last_active:
                if last_active[0]==name and last_active[0]==path:
                    self.combo_entry.set_active_iter(iter)
                else:
                    self.set_path('')
    def get_editable(self):
        return self.browse_dir_button.get_property("sensitive")
    def set_editable(self,editable=True):
##        self.combo_entry.child.set_editable(editable)
        self.combo_entry.set_sensitive(editable)##(gtk.SENSITIVITY_AUTO if editable else gtk.SENSITIVITY_OFF)
        self.browse_dir_button.set_sensitive(editable)
    def browse_path(self,button):
        if self.directory:
            path=directory_dialog(self.browse_prompt,self.get_path())
        else:
            path=file_dialog(self.browse_prompt,self.get_path())
        if path:
            self.set_path(path)
    def get_path(self):
        iter=self.combo_entry.get_active_iter()
        if iter:
            return self.model[iter][2]
        return self.combo_entry.child.get_text()
    def set_path(self,path):
        iter=self.model.get_iter_root()
        while iter:
            if io.equal(path,self.model[iter][2]):
                self.combo_entry.set_active_iter(iter)
                return
            iter=self.model.iter_next(iter)
        self.combo_entry.child.set_text(path)


class PathnameEntry(gtk.VBox):
    def __init__(self,default_path,label,browse_prompt,directory=True):
        gtk.VBox.__init__(self)
        self.browse_prompt=browse_prompt
        self.directory=directory
        box,self.path_entry,self.browse_dir_button=box_add(self,
            [(gtk.Entry(),True,None),
            (gtk.Button('...'),False,"clicked",self.browse_path)], #stock=gtk.STOCK_OPEN
            label)
    def set_editable(self,editable=True):
        self.path_entry.set_editable(editable)
        self.browse_dir_button.set_sensitive(editable)
    def browse_path(self,button):
        if self.directory:
            path=directory_dialog(self.browse_prompt,self.path_entry.get_text())
        else:
            path=file_dialog(self.browse_prompt,self.path_entry.get_text())
        if path:
            self.path_entry.set_text(path)
    def get_path(self):
        path=self.path_entry.get_text()
        path=path if path=='/' else path.rstrip('/')
        return path
    def set_path(self,path):
        self.path_entry.set_text(path)


def file_dialog(title='Choose an Image',default=''):
    fcd=gtk.FileChooserDialog(title=title, parent=None, action=gtk.FILE_CHOOSER_ACTION_OPEN,
        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK), backend=None)
    if not default:
        default=settings.home_dir
    fcd.set_current_folder(default)
    response=fcd.run()
    image_dir=''
    if response == gtk.RESPONSE_OK:
        image_dir=fcd.get_filename()
    fcd.destroy()
    return image_dir

def directory_dialog(title='Choose Image Directory',default=''):
    fcd=gtk.FileChooserDialog(title=title, parent=None, action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK), backend=None)
#    fcd.vbox.set_border_width(15)
    if not default:
        default=settings.home_dir
    fcd.set_current_folder(default)
    response=fcd.run()
    image_dir=''
    if response == gtk.RESPONSE_OK:
        image_dir=fcd.get_filename()
    fcd.destroy()
    return image_dir


def prompt_dialog(title,prompt,buttons=('_Yes','_No','_Cancel'),default=0):
    button_list=[]
    i=0
    for x in buttons:
        button_list.append(x)
        button_list.append(i)
        i+=1
    dialog = gtk.Dialog(title,None,gtk.DIALOG_MODAL,tuple(button_list))
    dialog.vbox.set_border_width(15)
    prompt_label=gtk.Label()
    prompt_label.set_label(prompt)
    prompt_label.set_line_wrap(True)
    prompt_label.set_width_chars(40)
    dialog.vbox.pack_start(prompt_label)
    dialog.vbox.show_all()
    dialog.set_default_response(default)
    response=dialog.run()
    dialog.destroy()
    return response

def entry_dialog(title,prompt,default_entry='',buttons=('_OK','_Cancel'),default=0):
    button_list=[]
    i=0
    for x in buttons:
        button_list.append(x)
        button_list.append(i)
        i+=1
    dialog = gtk.Dialog(title,None,gtk.DIALOG_MODAL,tuple(button_list))
    dialog.vbox.set_border_width(15)
    prompt_label=gtk.Label()
    prompt_label.set_label(prompt)
    prompt_label.set_line_wrap(True)
    prompt_label.set_width_chars(40)
    edit=gtk.Entry()
    if default_entry:
        edit.set_text(default_entry)
    dialog.vbox.pack_start(prompt_label)
    dialog.vbox.pack_start(edit)
    dialog.vbox.show_all()
    dialog.set_default_response(default)
    response=dialog.run()
    text=edit.get_text()
    dialog.destroy()
    return response,text

def date_range_entry_dialog(title,prompt,default_from=None,default_to=None,buttons=('_OK','_Cancel'),default=0):
    button_list=[]
    i=0
    for x in buttons:
        button_list.append(x)
        button_list.append(i)
        i+=1
    dialog = gtk.Dialog(title,None,gtk.DIALOG_MODAL,tuple(button_list))
    dialog.vbox.set_property('border-width',15) ##TODO: This doesn't work, find an alternative way to create spacing
    prompt_label=gtk.Label()
    prompt_label.set_label(prompt)
    prompt_label.set_line_wrap(True)
    prompt_label.set_width_chars(40)

    def check_cb(check,cal):
        cal.set_sensitive(check.get_active())

    date_box=gtk.HBox()
    cal_from=gtk.Calendar()
    cal_to=gtk.Calendar()
    if default_from:
        cal_from.select_month(default_from.month-1,default_from.year)
        cal_from.select_day(default_from.day)
    if default_to:
        cal_to.select_month(default_to.month-1,default_to.year)
        cal_to.select_day(default_to.day)
    from_box=gtk.VBox()
    from_check=gtk.CheckButton('From')
    from_check.set_active(True)
    from_box.pack_start(from_check)
    from_box.pack_start(cal_from)
    to_box=gtk.VBox()
    to_check=gtk.CheckButton('To')
    to_check.set_active(True)
    to_box.pack_start(to_check)
    to_box.pack_start(cal_to)
    date_box.pack_start(from_box)
    date_box.pack_start(to_box)
    from_check.connect('toggled', check_cb,cal_from)
    to_check.connect('toggled', check_cb,cal_to)

    dialog.vbox.pack_start(prompt_label)
    dialog.vbox.pack_start(date_box)
    dialog.vbox.show_all()
    dialog.set_default_response(default)
    response=dialog.run()
    if from_check.get_active():
        date_from=cal_from.get_date()
        date_from=date(date_from[0],date_from[1]+1,date_from[2])
    else:
        date_from=None
    if to_check.get_active():
        date_to=cal_to.get_date()
        date_to=date(date_to[0],date_to[1]+1,date_to[2])
    else:
        date_to=None
    dialog.destroy()
    return response,date_from,date_to



class BatchMetaDialog(gtk.Dialog):
    def __init__(self,item):
        gtk.Dialog.__init__(self,flags=gtk.DIALOG_NO_SEPARATOR|gtk.DIALOG_MODAL,
                         buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        self.set_title('Batch Tag Manipulation')
        tags=[t[0:2] for t in metadata.apptags if t[2]]
        rows=len(tags)
        table = gtk.Table(rows=rows, columns=3, homogeneous=False)
        self.item=item
        r=0
        for k,v in tags:
            try:
                val=metadata.app_key_to_string(k,item.meta[k])
                if not val:
                    val=''
            except:
                val=''
            self.add_meta_row(table,k,v,val,r)
            r+=1
        table.show_all()
        hbox=gtk.HBox()
        hbox.pack_start(table)
        hbox.show_all()
        self.vbox.pack_start(hbox)
        file_label=gtk.Label()
        file_label.set_label("Only checked items will be changed")
        file_label.show()
        self.vbox.pack_start(file_label)
        self.set_default_response(gtk.RESPONSE_ACCEPT)
    def meta_changed(self,widget,key):
        value=metadata.app_key_from_string(key,widget.get_text())
        self.item.set_meta_key(key,value)
    def toggled(self,widget,entry_widget,key):
        if widget.get_active():
            entry_widget.set_sensitive(True)
            value=metadata.app_key_from_string(key,entry_widget.get_text())
            self.item.set_meta_key(key,value)
        else:
            entry_widget.set_sensitive(False)
            try:
                del self.item.meta[key]
            except:
                pass
    def add_meta_row(self,table,key,label,data,row,writable=True):
        child1=gtk.CheckButton()
        child1.set_active(False)
        table.attach(child1, left_attach=0, right_attach=1, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        child2=gtk.Label(label)
        table.attach(child2, left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        child3=gtk.Entry()
        child3.set_property("activates-default",True)
        child3.set_text(data)
        child3.set_sensitive(False)
        child3.connect("changed",self.meta_changed,key)
        child1.connect("toggled",self.toggled,child3,key)
        table.attach(child3, left_attach=2, right_attach=3, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.EXPAND|gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)


class CollectionTypeList(gtk.TreeView):
    def __init__(self):
        self.model=gtk.ListStore(str,str)
        r=baseobjects.registered_collection_classes
        for c in r:
            if r[c].user_creatable:
                self.model.append([
                    r[c].type,
                    r[c].type_descr,
                        ])
        gtk.TreeView.__init__(self,self.model)
        self.set_headers_visible(False)
        self.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_NONE)
        cpt=gtk.CellRendererText()
        tvc=gtk.TreeViewColumn(None,cpt,text=1)
        self.append_column(tvc)


class NewCollectionDialog(gtk.Dialog):
    def __init__(self,type=None,pref_dict=None,title=None,button_label=None):
        '''
        Dialog displayed when user chooses to create a new collection
        If type is None
            The left part of the dialog displays a list of registered collection types
            The right side of the dialog displays the settings for the selected collection type
                Each collection class returns its own settings widget class with the member pref_dialog
            pref_dict is optional dictionary of initialized arguments to pass to the collection widget
        otherwise
            The collection settings widget of the specified type fills the dialog
            and the pref_dict is the optional initial values
        '''
        gtk.Dialog.__init__(self,flags=gtk.DIALOG_NO_SEPARATOR|gtk.DIALOG_MODAL)
        self.set_default_size(600,400)
        self.add_button("Cancel",gtk.RESPONSE_REJECT)
        if button_label==None:
            button_label="Create"
        self.create_button=self.add_button(button_label,gtk.RESPONSE_ACCEPT)
        self.create_button.set_sensitive(False)

        if title:
            self.set_title(title)
        else:
            self.set_title('Create a Collection')


        if type==None:
            self.types_list=CollectionTypeList()
            self.types_list.get_selection().connect("changed",self.changed_type)

            self.dialogs={}
            r=baseobjects.registered_collection_classes
            for c in r:
                w=r[c].add_widget
                if w:
                    print c
                    self.dialogs[c]=w(self,pref_dict)

            frame=gtk.Frame("Collection Types")
            frame.add(self.types_list)
            self.hbox=gtk.HBox()
            self.hbox.pack_start(frame,False,True,20)
            self.vbox.pack_start(self.hbox)
            sel=self.types_list.get_selection()
            self.ctype=None
            sel.select_path('0')
        else:
            self.dialogs={}
            self.ctype=type
            r=baseobjects.registered_collection_classes
            w=r[type].add_widget(self,pref_dict)
            self.dialogs[type]=w
            self.vbox.pack_start(w)

        self.vbox.show_all()

    def changed_type(self,sel):
        model,path=sel.get_selected()
        new_ctype=model[path][0]
        if self.ctype!=new_ctype:
            if self.ctype:
                self.hbox.remove(self.dialogs[self.ctype])
            self.ctype=new_ctype
            self.hbox.pack_start(self.dialogs[self.ctype],True,True,20)

    def get_values(self):
        if self.ctype:
            prefs=self.dialogs[self.ctype].get_values()
            if prefs:
                prefs['type']=self.ctype
            return prefs

    def set_values(self,prefs):
        if self.ctype:
            self.dialogs[self.ctype].set_values(prefs)
            return True
        return False

class PrefDialog(gtk.Dialog):
    def __init__(self,collection):
        gtk.Dialog.__init__(self,flags=gtk.DIALOG_NO_SEPARATOR|gtk.DIALOG_MODAL)
        prefs=collection.get_prefs()
        self.set_title(collection.type_descr+' Preferences')
        self.pref_box=collection.pref_widget(prefs)
        self.vbox.pack_start(self.pref_box,True,True,20)
        self.add_button("_Cancel",gtk.RESPONSE_REJECT)
        self.ok_button=self.add_button("_Accept Changes",gtk.RESPONSE_ACCEPT)
        self.vbox.show()

    def get_values(self):
        return self.pref_box.get_values()

    def set_values(self,val_dict):
        self.pref_box.set_values(val_dict)


class MetaDialog(gtk.Dialog):
    ##TODO: Use the widgetbuilder classes
    def __init__(self,item,collection):
        gtk.Dialog.__init__(self,flags=gtk.DIALOG_NO_SEPARATOR|gtk.DIALOG_MODAL)
        self.set_default_size(600,-1)
        vbox=gtk.VBox()
        a=gtk.Alignment(0,0,1,1)
        a.set_padding(16,16,16,16)
        a.add(vbox)
        self.vbox.pack_start(a)
#        self.vbox.pack_start(vbox,True,True)
        self.set_title('Edit Descriptive Info')
        tags=[t[0:2] for t in metadata.apptags if t[2]]
        rows=len(tags)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        table.set_col_spacings(16)
        self.item=item
        self.collection=collection
        r=0
        for k,v in tags:
            try:
                val=metadata.app_key_to_string(k,item.meta[k])
                if not val:
                    val=''
            except:
                val=''
            self.add_meta_row(table,k,v,val,r)
            r+=1
        table.show_all()
        hbox=gtk.HBox(False,16)
        hbox.pack_start(table,True,True)
        if item.thumb: ##todo: should actually retrieve the thumb (via callback) if not present
            self.thumb=gtk.Image()
#            self.thumb.set_alignment(0,0)
            self.thumb.set_from_pixbuf(item.thumb)
            hbox.pack_start(self.thumb)
        hbox.show_all()

        file_label=gtk.Label()
        file_label.set_markup('<b>%s</b>'%(item.uid,))
        file_label.show()
        file_label.set_alignment(0,0.5)

        vbox.pack_start(file_label,True,True,8)
        vbox.pack_start(hbox,True,True)
        self.vbox.show_all()
    def meta_changed(self,widget,key):
        value=metadata.app_key_from_string(key,widget.get_text())
        self.item.set_meta_key(key,value,self.collection)
    def add_meta_row(self,table,key,label,data,row,writable=True):
        child1=gtk.Label(label)
        child1.set_alignment(0,0.5)
        table.attach(child1, left_attach=0, right_attach=1, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=0, xpadding=0, ypadding=0)
        if writable:
            child2=gtk.Entry()
            child2.set_text(data)
            child2.connect("changed",self.meta_changed,key)
        else:
            child2=gtk.Label(data)
        table.attach(child2, left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.EXPAND|gtk.FILL, yoptions=0, xpadding=0, ypadding=0) #yoptions=gtk.EXPAND|gtk.FILL



