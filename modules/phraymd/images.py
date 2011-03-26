'''
legacy item class
'''

import baseobjects

class Item(list):
    '''An item is a class describing an image, including filename, pixbuf representations and related metadata'''
    def __init__(self,filename,mtime):
        filename=io.get_true_path(filename) ##todo: remove this - doesn't do anything and might break stuff in future
        list.__init__(self,[filename])
        self.filename=filename
        self.mtime=mtime
        self.thumb=None
        self.thumburi=None
        self.qview=None
        self.image=None
        self.meta_changed=False
        self.meta=None ##a copy of self.meta will be stored as self.meta_backup if self.meta_changed is True
        self.selected=False
        self.relevance=0
    def key(self):
        return 1
    def meta_revert(self):
        if self.meta_changed:
            self.meta=self.meta_backup
            del self.meta_backup
        self.meta_changed=False
    def mark_meta_saved(self):
        if self.meta_changed:
            del self.meta_backup
        self.meta_changed=False
    def set_meta_key(self,key,value,collection=None):
        if self.meta==False or self.meta==None:
            return None
        old=self.meta.copy()
        if not self.meta_changed:
            self.meta_backup=self.meta.copy()
            self.meta_changed=True
        if key in self.meta and key not in self.meta_backup and value=='':
            del self.meta[key]
        else:
            self.meta[key]=value
        pluginmanager.mgr.callback_collection('t_collection_item_metadata_changed',collection,self,old)
        if self.meta==self.meta_backup:
            del self.meta_backup
            self.meta_changed=False
        return self.meta_changed
    def set_meta(self,meta,collection=None):
        if not self.meta_changed:
            self.meta_backup=self.meta.copy()
            self.meta_changed=True
        old=self.meta
##PICKLED DICT
#        self.meta=PickledDict(meta)
        self.meta=meta
        pluginmanager.mgr.callback_collection('t_collection_item_metadata_changed',collection,self,old)
        if self.meta==self.meta_backup:
            del self.meta_backup
            self.meta_changed=False
        return self.meta_changed
    def __getstate__(self):
        odict = self.__dict__.copy() # copy the dict since we change it
        if odict['thumb']:
            odict['thumb']=None
        del odict['qview']
        del odict['image']
        del odict['selected']
        del odict['relevance']
        return odict
    def __setstate__(self,d):
        self.__dict__.update(d)   # update attributes
##PICKLED DICT
#        if type(self.meta)==dict:
#            self.meta=PickledDict(self.meta)
        self.thumb=None
        self.qview=None
        self.image=None
        self.selected=False
        self.relevance=0
    def convert(self):
        item=baseobjects.Item(self.filename)
        item.mtime=self.mtime
        item.thumb=self.thumb
        item.thumburi=self.thumburi
        item.qview=self.qview
        item.image=self.image
        item.meta_changed=self.meta_changed
        item.meta=self.meta
        item.selected=self.selected
        item.relevance=self.relevance
        return item
