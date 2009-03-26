import os
import os.path
import threading
import gobject

## contains a list of errors
## each error is a tuple (optype,imagepath,[destpath])
fileoperrors=[]

##todo: list of items could be the selection in a view/collection (so check selected bit before copy)


class Worker:
    def __init__(self):
        self.active=False
        self.kill=False

    def _delete(self):
        for i in range(len(self.items)):
            item=self.items[i]
            if self.kill:
                self.active=False
                return
            if self.cb:
                gobject.idle_add(self.cb,1.0*i/len(self.items),'Deleting '+item.filename)
            try:
                os.remove(item.filename)
            except:
                fileoperrors.append('del',item)
        if self.cb:
            gobject.idle_add(self.cb,2.0,'Finished Deleting')
        self.active=False

    def delete(self,items,cb,selected_only=True):
        if self.active:
            return False
        self.active=True
        self.kill=False
        if selected_only:
            self.items=[]
            for i in range(len(items)):
                item=items(i)
                if item.selected:
                    self.items.append(items(i))
        else:
            self.items=items
        self.cb=cb
        self.thread=threading.Thread(target=self._delete)
        self.thread.start()
        return True

    def _copy(self):
        for i in range(len(items)):
            item=self.items[i]
            if self.kill:
                self.active=False
                return
            if self.cb:
                gobject.idle_add(cb,1.0*i/len(items),'Copying '+item.filename)
            try:
                fin=open(item.filename,'rb')
                fout=open(item.filename,'wb') ##todo: check exists (and what about perms/attribs?)
                fin.write(fout.read())
            except:
                fileoperrors.append('copy',item,destdir)
        if self.cb:
            gobject.idle_add(self.cb,2.0,'Finished Copying')

    def copy(self,items,destdir,cb,selected_only=True):
        if self.active:
            return False
        self.active=True
        self.kill=False
        if selected_only:
            self.items=[]
            for i in range(len(items)):
                item=items(i)
                if item.selected:
                    self.items.append(items(i))
        else:
            self.items=items
        self.cb=cb
        self.thread=threading.Thread(target=self._copy)
        self.thread.start()
        return True

    def _move(self):
        for i in range(len(items)):
            item=self.items[i]
            if self.kill:
                self.active=False
                return
            if self.cb:
                gobject.idle_add(cb,1.0*i/len(items),'Moving '+item.filename)
            try:
                os.renames(item.filename,os.path.join(destdir,os.path.getfilname(item.filename)))
            except:
                fileoperrors.append('move',item,destdir)
        if self.cb:
            gobject.idle_add(self.cb,2.0,'Finished Moving')

    def move(self,items,destdir,cb,selected_only=True):
        if self.active:
            return False
        self.active=True
        self.kill=False
        if selected_only:
            self.items=[]
            for i in range(len(items)):
                item=items(i)
                if item.selected:
                    self.items.append(items(i))
        else:
            self.items=items
        self.cb=cb
        self.thread=threading.Thread(target=self._move)
        self.thread.start()
        return True

    def kill_op(self):
        self.kill=True

    def is_active(self):
        return self.active

worker=Worker()
