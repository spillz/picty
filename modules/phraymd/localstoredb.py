import threading
import sqlite3
import os.path


import baseobjects
import viewsupport
import monitor2 as monitor

col_prefs=('name','image_dirs','recursive','verify_after_walk','load_metadata','load_embedded_thumbs',
            'load_preview_icons','trash_location','thumbnail_cache','monitor_image_dirs')


class FilterFunc(object):
    def __call__(self,*args):
        return 1
class SortFunc(object):
    def __call__(self,*args):
        return 1

class SQLconnection(object):
    '''
    light wrapper around multiple SQL connection objects, one for each thread in the application
    '''
    def __init__(self,filename):
        self.filename=filename
        self.connections={}
        self.functions=[]
    def create_function(self,name,num_params,func):
        self.functions.append((name,num_params,func))
        for c in self.connections:
            self.connections[c].create_function(name,num_params,func)
    def conn_new_thread(self):
        print 'creating new connection on',threading.current_thread(),'for',self.filename
        conn=sqlite3.connect(self.filename)
        print 'created connection',conn
        self.connections[threading.current_thread()]=conn
        for f in self.functions:
            conn.create_function(*f)
        return conn
    def __getattr__(self,name,*args):
        try:
            print 'connection attr',name
            connection_method=self.connections[threading.current_thread()].__getattribute__(name)
        except KeyError:
            conn=self.conn_new_thread()
            connection_method=conn.__getattribute__(name)
        return connection_method


class SQLcursor(object):
    '''
    light wrapper around multiple SQL curser objects, one for each thread in the application
    '''
    def __init__(self,connection):
        self.connection=connection
        self.cursors={}
    def execute(self,*args):
        ex=self.__getattr__('execute')
        while True:
            try:
                ex(*args)
                return
            except sqlite3.OperationalError:
                print 'db busy'
    def __getattr__(self,name):
        try:
            print 'cursor attr',name,threading.current_thread().ident
            cursor_method=self.cursors[threading.current_thread()].__getattribute__(name)
        except KeyError:
            print 'creating new cursor',threading.current_thread()
            cursor=self.connection.cursor()
            print 'created cursor',cursor
            self.cursors[threading.current_thread()]=cursor
            cursor_method=cursor.__getattribute__(name)
        return cursor_method


class LocalStoreDB(baseobjects.CollectionBase):
    type='LOCALSTORE-SQLDB'
    type_descr='LOCALSTORE (SQL Database)'
    def __init__(self,prefs):
        baseobjects.CollectionBase.__init__(self,prefs)
        self.type='LOCALSTORE-SQLDB'
        self.type_descr='LOCALSTORE (SQL Database)'
        self.id=self.data_file()
        self.view_class=LocalStoreDBView
        self.new_menu_entry='New Collection Database' #set to a string prompt that will be shown on menu allowing user to add a new collection
        self.persistent=True #whether the collection is stored to disk when closed
        self.conn=None
        self.cursor=None
        self.sort_func=SortFunc()
        self.filter_func=FilterFunc()

        self.name=''#name displayed to the user
        self.pixbuf=None#icon to display in the interface (maybe need more than one size)
        self.id=None #unique id of the collection
        self.is_open=False #set by the owner to specify whether this collection is open or closed
        self.numselected=0 #number of items in the collection with a "selected" state

        self.image_dirs=[]
        self.recursive=True
        self.verify_after_walk=True
        self.load_metadata=True #image will be loaded into the collection and view without metadata
        self.load_embedded_thumbs=False #only relevant if load_metadata is true
        self.load_preview_icons=False #only relevant if load_metadata is false
        self.trash_location=None #none defaults to <collection dir>/.trash
        self.thumbnail_cache=None #use gnome/freedesktop or put in the image folder
        self.monitor_image_dirs=True

        ## the collection optionally has a filesystem monitor and views (i.e. subsets) of the collection of images
        self.monitor=None
        self.monitor_master_callback=None
        self.browser=None

        if prefs:
            self.set_prefs(prefs)
        self.id=self.name
        if os.path.exists(self.data_file()):
            self.open()
        else:
            self.create_new()
            self.open()


    def create_new(self):
        self.conn=SQLconnection(self.data_file())
        self.conn.create_function('filter_func',1,self.filter_func)
        self.conn.create_function('sort_func',1,self.sort_func)

        self.cursor=SQLcursor(self.conn)
        self.cursor.execute('''create table items
                    (id text, mtime text, meta blob, thumb_uri text)''')
        self.cursor.execute('''create index item_index on items (id)''')
        self.cursor.close()
        self.conn.close()
    def open(self):
        self.conn=SQLconnection(self.data_file())
        self.cursor=SQLcursor(self.conn)
        self.conn.create_function('filter_func',1,self.filter_func)
        self.conn.create_function('sort_func',1,self.sort_func)
        print 'inserting dummy item'
        self.cursor.execute('''insert into items values (?,?,?,?)''',('/home/damien/IMGP3306.JPG',0,'',''))
        print 'inserted dummy item'
        return True
        try:
            self.conn=SQLconnection(self.data_file())
            self.cursor=SQLcursor(self.conn)
            self.conn.create_function('filter_func',1,self.filter_func)
            self.conn.create_function('sort_func',1,self.sort_func)
            print 'inserting dummy item'
            self.cursor.execute('''insert into items values (?,?,?,?)''',('/home/damien/IMGP3306.JPG',0,{},''))
            print 'inserted dummy item'
            return True
        except:
            return False
    def close(self):
        self.cursor.close()
        self.conn.close()
        ##required overrides (must be overridden to implement a collection)
    def pref_gui_box(self):
        pass
    def item_metadata_update(self,item):
#        self.cursor.execute('''delete from items where id=?''',(item.id,))
#        self.cursor.execute('''insert into items values (?,?,?,?)''',(item.id,item.mtime,item.meta,item.thumburi))
        self.cursor.execute('''update items set id=?,mtime=?,meta=?,thumb_uri=? where id=?''',(item.uid,item.mtime,item.meta,item.thumburi,item.id))
    def add(self,item,add_to_view=False):
        ##todo: have to check that item with the same id isn't already present
        ##add_to_view is ignored -- the database will automatically add items to connected views
        print 'adding item',item.uid
        self.cursor.execute('''insert into items values (?,?,?,?)''',(item.uid,item.mtime,item.meta,item.thumburi))
        print 'about to commit'
#        self.cursor.commit()
        print 'committed'
    def find(self,item):
        print 'db find requested'
        self.cursor.execute('''select * from items where id=?''',(item.uid,))
        items=self.cursor.fetchall()
        if len(items)>0:
            itdata=items[0]
            item=baseobjects.Item(itdata[0])
            item.mtime=itdata[1]
            item.meta=itdata[2]
            item.thumburi=itdata[3]
            return item
    def delete(self,item):
        self.cursor.execute('''delete from items where id=?''',(item.uid,))
        self.cursor.commit()
        pass
    def __call__(self,ind):
        print 'db call requested'
        self.__getitem__(ind)
    def __iter__(self):
        print 'db iter requested'
        self.cursor.execute('''select * from items''')
        items=self.cursor.fetchall()
        for i in items:
            item=baseobjects.Item(i[0])
            item.mtime=i[1]
            item.meta=i[2]
            item.thumburi=i[3]
            yield item
    def __getitem__(self,ind):
        print 'db get item requested'
        self.cursor.execute('''select * from items limit 1 offset ?''',(ind,))
        items=self.cursor.fetchall()
        if len(items)>0:
            itdata=items[0]
            item=baseobjects.Item(itdata[0])
            item.mtime=itdata[1]
            item.meta=itdata[2]
            item.thumburi=itdata[3]
            return item
    def get_all_items(self): #was get_items
        print 'db get items'
        pass
    def empty(self,empty_views=True):
        self.cursor.fetchall('''delete from items''')
    def __len__(self):
        print 'db len requested'
        query='''select count(id) from items'''
        self.cursor.execute(query)
        result=self.cursor.fetchall()
        for r in result:
            return r[0]

    def set_prefs(self,prefs):
        for p in col_prefs:
            if p in prefs:
                self.__dict__[p]=prefs[p]

    def get_prefs(self):
        prefs={}
        for p in col_prefs:
            prefs[p]=self.__dict__[p]
        return prefs

    def start_monitor(self,callback):
        if self.monitor_image_dirs:
            self.monitor_master_callback=callback
            self.monitor=monitor.Monitor(self.image_dirs,self.recursive,self.monitor_callback)

    def end_monitor(self):
        if self.monitor!=None and self.monitor_image_dirs:
            self.monitor.stop()
            self.monitor=None

    def monitor_callback(self,path,action,is_dir):
        self.monitor_master_callback(self,path,action,is_dir)


class LocalStoreDBView(baseobjects.ViewBase):
    def __init__(self,key_cb=viewsupport.get_mtime,items=[],collection=None):
        baseobjects.ViewBase.__init__(self,key_cb,items,collection)
        self.cursor=SQLcursor(collection.conn)
        self.view_name='main_view'
        self.sort_func_name=key_cb
        self.filter_func_name=viewsupport.none_filter
        self.cursor.execute('''select * from SQLITE_MASTER where type='table' and name=?;''',(self.view_name,))
        r=self.cursor.fetchall()
        if not r:
            self.build_view()
    def build_view(self):
        ##todo: how to keep table sorted?
        query='''create table %s as select sort_func(meta) as sortkey,* from items where filter_func(meta)>0 order by sortkey'''%(self.view_name)
        self.cursor.execute(query)
        query='''create trigger %s_delete delete on items
                                begin
                                    delete from %s where id=old.id;
                                end
                            '''%(self.view_name,self.view_name)
        self.cursor.execute(query)
        query='''create trigger %s_insert insert on items when filter_func(new.meta)>0
                                begin
                                    insert into %s values (sort_func(new.meta),new.id,new.mtime,new.meta,new.thumb_uri);
                                end
                            '''%(self.view_name,self.view_name)
        self.cursor.execute(query)
        query='''create trigger %s_update update on items when filter_func(new.meta)>0
                                begin
                                    update %s set sortkey=sort_func(new.meta),id=new.id,mtime=new.mtime,
                                        meta=new.meta,thumb_uri=new.thumb_uri
                                        where id=old.id;
                                end
                            '''%(self.view_name,self.view_name)
        self.cursor.execute(query)
        query='''create index %s_index on %s (sortkey)'''%(self.view_name,self.view_name)
        self.cursor.execute(query)

    def __call__(self,ind):
        self.__getitem__(ind)

    def __getitem__(self,ind):
        query='''select * from %s limit 1 offset ? order by sortkey'''%(self.view_name,)
        self.cursor.execute(query,(ind,))
        items=self.cursor.fetchall()
        if len(items)>0:
            itdata=items[0]
            item=baseobjects.Item(itdata[0])
            item.mtime=itdata[1]
            item.meta=itdata[2]
            item.thumburi=itdata[3]
            return item

    def set_filter(self,expr):
        self.filter_tree=sp.parse_expr(TOKENS[:],expr,literal_converter)

    def clear_filter(self,expr):
        self.filter_tree=None
# THESE PROBABLY AREN'T NEEDED BECAUSE WE USE TRIGGERS ON THE COLLECTION TO ADD ITEMS TO THE VIEW
#    def add(self,key,item,apply_filter=True):
#    def remove(self,key,item):
#    def add_item(self,item,apply_filter=True):
#    def del_item(self,item):
#    def del_ind(self,ind):

    def find_item(self,item):
        query='''select count(sortkey) from %s where sortkey<?'''%(self.view_name,)
        self.cursor.execute(query,(item.uid,))
        result=self.cursor.fetchall()
        for r in result:
            return r[0]
        return -1

    def __getitem__(self,index):
        self.__call__(index)

    def __call__(self,index):
        query='''select * from %s order by sortkey limit 1 offset ?'''%(self.view_name,)
        self.cursor.execute(query,(index,))
        result=self.cursor.fetchall()
        for itdata in result:
            item=baseobjects.Item(itdata[0])
            item.mtime=itdata[1]
            item.meta=itdata[2]
            item.thumburi=itdata[3]
            return item

    def __len__(self):
        query='''select count(sortkey) from %s'''%(self.view_name,)
        self.cursor.execute(query)
        result=self.cursor.fetchall()
        for r in result:
            return r[0]

    def get_items(self,first,last):
        query='''select * from %s order by sortkey limit ? offset ?'''%(self.view_name,)
        self.cursor.execute(query,(last-first,first))
        result=self.cursor.fetchall()
        items=[]
        for itdata in result:
            item=baseobjects.Item(itdata[0])
            item.mtime=itdata[1]
            item.meta=itdata[2]
            item.thumburi=itdata[3]
            items.append(item)
        return items

    def get_selected_items(self):
        return []
    def empty(self):
        query='''delete from %s'''%(self.view_name,)
        self.cursor.execute(query)

baseobjects.register_collection(LocalStoreDB.type,LocalStoreDB)
baseobjects.register_view(LocalStoreDB.type,LocalStoreDBView)
