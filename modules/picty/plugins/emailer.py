#!/usr/bin/python

'''

    picty Email plugin
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

'''
picty photo emailer
    SMTP only
    shows an email page with to, subject, message entries and a send button
    will email all selected messages in the current view
    config to set SMTP preferences
    shows an error in the message box if the message cannot be sent

TODO:
    add a history log showing all successful and unsuccessful emails including what files were sent
    remember contacts (and offer completion hint in the toolbar)
    input validation
    clear mail form after send (and hide the dialog)

'''

import gtk
import gobject

from picty import settings
from picty import pluginbase
from picty import backend
from picty import imagemanip
from picty.uitools import widget_builder as wb
from picty.fstools import io

#!/usr/bin/python

import keyring
import smtplib
import email
import os

KEYRING_SERVICE_NAME = 'picty-emailer'

def send_mail(send_from, send_to, subject, text, files, username, password, server="localhost"):
#    assert type(send_to)==list
    assert type(files)==list

    msg = email.MIMEMultipart.MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = send_to #', '.join(send_to)
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach( email.MIMEText.MIMEText(text) )

    for f in files:
        part = email.MIMEBase.MIMEBase('application', "octet-stream")
        part.set_payload( open(f,"rb").read() )
        email.Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
        msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.ehlo()
    smtp.starttls()
    smtp.login(username,password)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()

class SendMailJob(backend.WorkerJob):
    def __init__(self,worker,collection,browser,plugin,prefs):
        backend.WorkerJob.__init__(self,'EMAIL',780,worker,collection,browser)
        self.plugin=plugin
        self.collection = collection
        self.stop=False
        self.countpos=0
        self.items=None
        self.prefs=prefs
        self.images = []
##        self.plugin.mainframe.tm.queue_job_instance(self)

    def cancel(self,shutdown=False):
        if not shutdown:
            gobject.idle_add(self.plugin.transfer_cancelled)

    def __call__(self):
        jobs=self.worker.jobs
        worker=self.worker
        i=self.countpos
        collection=self.collection

        send_from = self.prefs['from']
        send_to = self.prefs['to']
        subject = self.prefs['subject']
        text = self.prefs['message']
        size = self.prefs['size']
        server = self.prefs['server']
        username = self.prefs['username']
        password = self.prefs['password']
        strip_metadata = self.prefs['strip_metadata']
        apply_edits = self.prefs['apply_edits']

        if self.items==None:
            self.items=self.collection.get_active_view().get_selected_items()
            self.count=len(self.items)
        while len(self.items)>0 and jobs.ishighestpriority(self) and not self.stop:
            item=self.items.pop()
            if self.browser:
                gobject.idle_add(self.browser.update_status,1.0*i/self.count,'Preparing Images - %i of %i'%(i,self.count))
            prefs=self.prefs
            im = imagemanip.get_jpeg_or_png_image_file(item,self.collection,size,strip_metadata,apply_edits)
            if im is not None:
                self.images.append(im)
            i+=1
        self.countpos=i
        if len(self.items)==0:
            if len(self.images)==0: ##nothing to do
                gobject.idle_add(self.browser.update_status,1.0,'Nothing to send')
                self.prefs['error'] = 'No images could be sent (check your selected images)'
                gobject.idle_add(self.plugin.email_failed,self.prefs)
                return True
            if self.browser:
                gobject.idle_add(self.browser.update_status,0.99,'Sending Email ...')
            ## Send email
            try:
                send_mail(send_from, send_to, subject, text, self.images, username, password, server)
                self.prefs['error'] = 'Email sent'
                gobject.idle_add(self.plugin.email_completed,self.prefs)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.prefs['error'] = 'Email failed with error message %s'%(e.message)
                gobject.idle_add(self.plugin.email_failed,self.prefs)
                pass ##TODO: notify UI of error
            ## TODO: Clean up images - only remove the temporary copies (commented code below would delete all of the images - not what we want!!)
#            for im in images:
#                io.remove_file(im)
            gobject.idle_add(self.browser.update_status,1.0,'Email Send Done')
            return True
        return False



class EmailPlugin(pluginbase.Plugin):
    name='Email'
    display_name='Photo Emailer'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        pass

    def plugin_init(self,mainframe,app_init):
        self.mainframe=mainframe
        panel=mainframe.float_mgr.add_panel('Email','Show or hide the email panel','picty-emailer')
        self.emailframe=EmailFrame(self)
        panel.vbox.pack_start(self.emailframe)
        data = settings.load_addon_prefs('emailer')
        if data is not None:
            self.emailframe.set_form_data(data)

    def plugin_shutdown(self,app_shutdown):
        data = self.emailframe.get_form_data()
        settings.save_addon_prefs('emailer',data)
        if not app_shutdown:
            self.mainframe.float_mgr.remove_panel('Email')
            del self.emailframe
            del self.mainframe
            ##todo: delete references to widgets


class EmailFrame(wb.Notebook):
    def __init__(self,plugin):
        self.mainframe = plugin.mainframe
        header_box = wb.HBox([
                ('to_subj',wb.LabeledWidgets([
                    ('to','To:',wb.Entry('someone@email.com')),
                    ('subject','Subject:',wb.Entry('Photos')),
                    ]),True),
                ('send',wb.Button('SEND'),False,True)
                ])

        error_bar = wb.HBox([('error',wb.gtk_widget(gtk.Label)(),True),('close_box',wb.gtk_widget(gtk.Button)('Hide'),False)])
        mail_page = ('email_page','Email',
            wb.VBox([
            ('error_bar',error_bar,False),
            ('header_info',header_box,False),
            ('message',wb.ScrollingTextView()),
            (gtk.Label('All selected images in the current browser view will be sent'),False)
            ])
            )
        config_page = ('config_page','Mail Configuration',
                wb.LabeledWidgets([
                ('username','Username:',wb.Entry('you@email.com')),
                ('password','Password:',wb.Button('Enter a password...'),False,False),
                ('server','SMTP Server:',wb.Entry('smtp.email.com')),
                ('size','Maximum Image Size:',wb.Entry('1024')),
                ('apply_edits','Apply Image Edits:',wb.ComboBox(['Yes','No'])),
                ]))
        wb.Notebook.__init__(self,[mail_page,config_page])
        self.show_all()
        self['email_page']['error_bar'].hide()
        self['email_page']['error_bar']['error'].set_property("wrap",True)
        self['email_page']['error_bar']['close_box'].connect("clicked",self.error_close)
        self['email_page']['error_bar']['close_box'].set_image(gtk.image_new_from_stock(gtk.STOCK_CLOSE,gtk.ICON_SIZE_MENU))
        header_box['send'].connect("clicked",self.do_send)
        self['config_page']['password'].connect("clicked",self.password_dialog)

    def error_close(self,button):
        self['email_page']['error_bar'].hide()

    def email_failed(self,data):
        print 'Email failed!'
        print data
        self['email_page'].set_sensitive(True)
        self['email_page']['error_bar'].show()
        self['email_page']['error_bar']['error'].set_text(data['error'])
        keyring.delete_password(KEYRING_SERVICE_NAME,data['username']) #assume that the problem was a bad password

    def email_completed(self,data):
        print 'Email succeeded!'
        print data
        self['email_page']['error_bar'].show()
        self['email_page']['error_bar']['error'].set_text(data['error'])
#        d = self.get_form_data()
#        d['email_page']['header_info']['to_subj']['to'] = ''
#        d['email_page']['header_info']['to_subj']['subject'] = ''
#        d['email_page']['message'] = ''
#        self.set_form_data(d)
        self['email_page'].set_sensitive(True)

    def do_send(self,button):
        print 'doing the send'
        d = self.get_form_data()
        prefs = d['config_page']
        prefs.update(d['email_page'])
        prefs['to'] = prefs['header_info']['to_subj']['to']
        prefs['from'] = prefs['username']
        prefs['subject'] = prefs['header_info']['to_subj']['subject']
        prefs['strip_metadata'] = False
        prefs['size'] = int(prefs['size'])
        prefs['apply_edits'] = prefs['apply_edits']==0
        del prefs['header_info']
        print prefs

        password = keyring.get_password(KEYRING_SERVICE_NAME,prefs['username'])
        if password is None:
            password = self.password_dialog()
        if password is None or password =='':
            self['email_page']['error_bar'].show()
            self['email_page']['error_bar']['error'].set_text('You must enter a password')
            return

        prefs['password'] = password

        self['email_page'].set_sensitive(False)
        smj = SendMailJob(self.mainframe.tm,self.mainframe.active_collection,self.mainframe.active_collection.browser,self,prefs)
        self.mainframe.tm.queue_job_instance(smj)

    def password_dialog(self,*args):
        d=wb.ModalDialog([
                        ('password',wb.LabeledEntry('Password:')),
                        ('remember',wb.CheckBox('Store in keyring')),
                        ],
                        title='Enter a Password')
        ##TODO Only allow OK if password is non-empty
        fd = self.get_form_data()
        user = fd['config_page']['username']

        d['password'].entry.set_visibility(False)
        password = keyring.get_password(KEYRING_SERVICE_NAME,user)
        if password is not None:
            d['password'].entry.set_text(password)
            d['box']['remember'].set_active(True)

        response=d.run()
        dfd = d.get_form_data()
        d.destroy()
        if response == 1:
            password = dfd['password']
            remember = dfd['remember']
            if remember and password != '':
                keyring.set_password(KEYRING_SERVICE_NAME, user, password)
            elif not remember:
                keyring.delete_password(KEYRING_SERVICE_NAME, user)
            return password
        return None

if __name__ == '__main__':
    pass

