import os
import os.path
import pyinotify


if '__version__' in dir(pyinotify) and pyinotify.__version__>='0.8.0':
    mask = (pyinotify.IN_DELETE |
            pyinotify.IN_CREATE |
            pyinotify.IN_DONT_FOLLOW |
            pyinotify.IN_MODIFY|
            pyinotify.IN_MOVED_FROM|
            pyinotify.IN_MOVED_TO)  # watched events

    class Monitor(pyinotify.ProcessEvent):
        def __init__(self,dirs,recursive,cb):
            pyinotify.ProcessEvent.__init__(self)
            self.cb=cb
            self.wm=pyinotify.WatchManager()
            self.notifier = pyinotify.ThreadedNotifier(self.wm, self)
            self.notifier.start()
            self.wd=[]
            self.recursive=recursive
            for d in dirs:
                self.wd.append(self.wm.add_watch(d, mask, rec=recursive, auto_add=True))
        def stop(self):
            try:
                for wd in self.wd:
                    self.wm.rm_watch(wd.values(),rec=self.recursive)
                self.notifier.stop() ##todo: should be checking if there are any other watches still active?
            except:
                print 'Error removing watch'
                import traceback,sys
                print traceback.format_exc(sys.exc_info()[2])
        def process_IN_MODIFY(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'MODIFY',event.dir)
        def process_IN_MOVED_FROM(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'MOVED_FROM',event.dir)
        def process_IN_MOVED_TO(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'MOVED_TO',event.dir)
        def process_IN_CREATE(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'CREATE',event.dir)
        def process_IN_DELETE(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'DELETE',event.dir)
        def process_default(self, event=None):
            pass
else:
    mask = (pyinotify.EventsCodes.IN_DELETE |
            pyinotify.EventsCodes.IN_CREATE |
            pyinotify.EventsCodes.IN_DONT_FOLLOW |
            pyinotify.EventsCodes.IN_MODIFY|
            pyinotify.EventsCodes.IN_MOVED_FROM|
            pyinotify.EventsCodes.IN_MOVED_TO)  # watched events

    class Monitor(pyinotify.ProcessEvent):
        def __init__(self,dirs,recursive,cb):
            pyinotify.ProcessEvent.__init__(self)
            self.cb=cb
            self.wm=pyinotify.WatchManager()
            self.notifier = pyinotify.ThreadedNotifier(self.wm, self)
            self.notifier.start()
            self.wd=[]
            self.recursive=recursive
            for d in dirs:
                self.wd.append(self.wm.add_watch(d, mask, rec=recursive, auto_add=True))
        def stop(self):
            try:
                for wd in self.wd:
                    self.wm.rm_watch(wd.values(),rec=self.recursive)
                self.notifier.stop() ##todo: should be checking if there are any other watches still active?
            except:
                print 'Error removing watch'
                import traceback,sys
                print traceback.format_exc(sys.exc_info()[2])
        def process_IN_MODIFY(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'MODIFY',event.is_dir)
        def process_IN_MOVED_FROM(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'MOVED_FROM',event.is_dir)
        def process_IN_MOVED_TO(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'MOVED_TO',event.is_dir)
        def process_IN_CREATE(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'CREATE',event.is_dir)
        def process_IN_DELETE(self, event):
            path=os.path.join(event.path, event.name)
            self.cb(path,'DELETE',event.is_dir)
        def process_default(self, event=None):
            pass
