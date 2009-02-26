import time
import os
from pyinotify import WatchManager, Notifier, ThreadedNotifier, EventsCodes, ProcessEvent

wm=WatchManager()

mask = EventsCodes.IN_DELETE | EventsCodes.IN_CREATE |EventsCodes.IN_DONT_FOLLOW |EventsCodes.IN_MODIFY|EventsCodes.IN_MOVED_FROM|EventsCodes.IN_MOVED_TO  # watched events

class PTmp(ProcessEvent):
    def process_IN_DELETE(event):
        path=os.path.join(event.path, event.name)
        print "Deleted: %s" %  path
#        if os.path.isdir(path):
#            wm.rm_watch(path,mask,rec=True)
    def process_IN_MODIFY(self, event):
        path=os.path.join(event.path, event.name)
        print "Modify: %s" %  path
    def process_IN_MOVED_FROM(self, event):
        path=os.path.join(event.path, event.name)
        print "Moved out: %s" %  path
#        if os.path.isdir(path):
#            wm.rm_watch(path,mask,rec=True)
    def process_IN_MOVED_TO(self, event):
        path=os.path.join(event.path, event.name)
        print "Moved in: %s" %  path
#        if os.path.isdir(path):
#            wm.add_watch(path,mask,rec=True)
    def process_IN_CREATE(self, event):
        path=os.path.join(event.path, event.name)
        print "Create: %s" %  path
#        if os.path.isdir(path):
#            wm.add_watch(path,mask,rec=True)
    def process_IN_DELETE(self, event):
        path=os.path.join(event.path, event.name)
        print "Remove: %s" %  path
#        if os.path.isdir(path):
#            wm.rm_watch(path,mask,rec=True)

notifier = ThreadedNotifier(wm, PTmp())
notifier.start()

wdd = wm.add_watch('/tmp', mask, rec=True)
while True:
    time.sleep(1)

wm.rm_watch(wdd['/tmp'], rec=True)
notifier.stop()



#
#
#
#import gnomevfs
#import gobject
#import threading
#import os
#
#gobject.threads_init()
#
#class Monitor:
#    def __init__(self):
#        self.interrupt_lock=threading.Lock()
#        self.thread_notify=False
#        (self.pipe_r,self.pipe_w)=os.pipe()
#        self.pipe_r_channel=gobject.io_channel_unix_new(self.pipe_r);
#    def run(self):
#        self.interrupt_lock.acquire();
#        self.thread_notify=False;
#        context=gobject.MainContext()
#        loop=gobject.MainLoop(context)
#        result=gobject.io_add_watch(self.pipe_r_channel, gobject.IO_IN, tn_callback);
#
#        for uri in self.paths:
#            monhandle=gnomevfs.monitor_add(uri, gnomevfs.MONITOR_DIRECTORY, monitor_callback)
#            if(monhandle):
#                monhandles.append(monhandle)
#            else:
#                monhandles.append(None)
#                ##TODO: Log an error
#        //TODO: Add a timer for killing singleshot instances
#        self.interrupt_lock.release();
#
#        loop.run()
#
#        for monhandle in self.monhandles:
#            if monhandle:
#                gnomevfs.monitor_cancel(monhandle);
#
#        status=gobject.io_channel_shutdown(self.pipe_r_channel, True, err);
#
#        self.interrupt_lock.release()();
#        return NULL;
#    }
##    ~DirMonitorThread()
##    {
##        g_main_loop_quit(loop);
##        if(IsRunning())
##            Wait();//Delete();
##        close(m_msg_rcv);
##        close(m_msg_send);
##    }
#    def monitor_callback(self, arg1, arg2, arg3, arg4):
#        #ARGS SHOULD BE: GnomeVFSMonitorHandle *handle, const gchar *monitor_uri, const gchar *info_uri, GnomeVFSMonitorEventType event_type, gpointer user_data)
#        print arg1,arg2,arg3
##        int action=0;
##        switch(EventType)
##        {
##            case GNOME_VFS_MONITOR_EVENT_CHANGED:
##                action=MONITOR_FILE_CHANGED;
##                break;
##            case GNOME_VFS_MONITOR_EVENT_DELETED:
##                action=MONITOR_FILE_DELETED;
##                break;
##            case GNOME_VFS_MONITOR_EVENT_STARTEXECUTING:
##                action=MONITOR_FILE_STARTEXEC;
##                break;
##            case GNOME_VFS_MONITOR_EVENT_STOPEXECUTING:
##                action=MONITOR_FILE_STOPEXEC;
##                break;
##            case GNOME_VFS_MONITOR_EVENT_CREATED:
##                action=MONITOR_FILE_CREATED;
##                break;
##            case GNOME_VFS_MONITOR_EVENT_METADATA_CHANGED:
##                action=MONITOR_FILE_ATTRIBUTES;
##                break;
##        }
##        if(action&m_notifyfilter)
##        {
##            wxDirectoryMonitorEvent e(mon_dir->c_str(),action,uri);
##            m_parent->AddPendingEvent(e);
##        }
#    def UpdatePaths(self,paths):
#        interrupt_lock.Lock();
#        m_update_paths.Empty();
#        for(unsigned int i=0;i<paths.GetCount();i++)
#            m_update_paths.Add(paths[i].c_str());
#        GError *err;
#        //GIOStatus s=g_io_channel_write_unichar(m_msg_send, 'm',&err);
#        char m='m';
#        gsize num;
#        write(m_msg_send,&m,1);
#        //flush(m_msg_send);
#//        GIOStatus s=g_io_channel_write_chars(m_msg_send, &m, 1, &num,&err);
#//        if(s!=G_IO_STATUS_NORMAL)
#//            wxMessageBox(_("Write error!"));
#//        s=g_io_channel_flush(m_msg_send, &err);
#//        if(s!=G_IO_STATUS_NORMAL)
#//            wxMessageBox(_("Flush error!"));
#        interrupt_lock.Unlock();
