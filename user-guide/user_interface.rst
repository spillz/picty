User Interface
==============

Picty has a deliberately minimalistic user interface. There is no menu bar,
just a toolbar, and much of the interface can be hidden away when it is not
in use. Picty works nicely on small screen and large. The interface is
currently very mouse centric. Toolbars and information displays pop up
over images when you hover the mouse over them offering commonly used
actions. Often you can also right click on parts of the interface to see
other options. Currently, you can use keyboard shortcuts to control
some things, but eventually you will be able to use the keyboard for
everything if that's your thing.

The Main Window
---------------

The main window has five main components, two of which may be hidden.
The picture below shows the main window after opening a collection
and viewing an image:

.. image :: screenshots/main-window-annotated-complete.png

The five components of the interface are:

1. **Collections Notebook**: Collections are displayed in a "tabbed"
    notebook, with each page of the notebook representing an open
    collection. This allows you to have more than one collection open
    at a time! The content of each page in the notebook is an Image
    Browser for that collection and the global Image Viewer. The
    last tab of the notebook (the one with a "+" sign) is the start
    page that you will use to create, open, close, delete and manage
    your photo collections and devices.

2. **Image Browser**: The image browser displays thumbnails of all
   (or a subset) of the photos and videos in your collection or device.
   As you    move the mouse over the thumbnails you will see additional
   information    displayed about the image (e.g. the date it was shot,
   and exposure info) and some buttons for common actions (e.g. delete,
   rotate, edit desciptive information). You can select individual images by clicking
   on them, and then right click on the selection to work on images in
   batch. You can drag individual images or selections to the desktop
   or to other applications. You can restrict the images in the browser
   to a subset of images (called a ``View``, not to be confused with
   the **Image Viewer**) in the collections using the search box in the
   **Main Toolbar**.

3. **Image Viewer**: The image viewer displays an enlarged version of the
    photos in your collection. You can view images in the image browser
    by double clicking the mouse on them in the image browser (or by
    pressing the ``Enter`` key). By default, the viewer will be displayed
    along side the browser in the main window, but it can also be displayed
    in fullscreen (press ``Enter``). The viewer will popup a viewer toolbar
    and information about the image if you move the mouse inside the viewer.
    (To see the viewer toolbar, move the mouse toward the top of the image
    view)

4. **Main Toolbar**: The main toolbar contains a variety of actions that
    generally affect the collection as a whole or the current view of the
    collection. For example, there are actions to rescan the collection,
    save changes to image metadata, and to search for images. There are
    also shortcuts for various plugins including an email plugins, a
    mapping plugin, and a plugin that lets you transfer images between
    collections.

5. **Sidebar**: The sidebar displays a tree view of the tag and folder
    layout of the collection, in the "Tag" and "Folder" tabs, respectively.
    picty has a very rich tagging interface that makes it easy to manage
    the tags (i.e. keywords) associated with your images. For example,
    see all of the images associated with a tag is as simple as double
    clicking on that tag in the sidebar. You can also browse the items
    in a particular folder by double clicking on the folder in the "Folder"
    tab.

6. **Status Bar**: The status bar displays summary information about the
    number of images in the collection and in the current view of the
    collection. It also shows a spinner bar during background activity,
    such as scanning the collection for new images.


Keyboard Shortcuts
------------------

Here are the current keyboard shortcuts. More shortcuts will be added over
time until picty can be completely controlled via the keyboard.

+------------------+----------------------------------------------------+
| **Navigation**                                                        |
+------------------+----------------------------------------------------+
+ ``Up Arrow``     | Scroll active browser window up                    |
+------------------+----------------------------------------------------+
+ ``Down Arrow``   | Scroll active browser window down                  |
+------------------+----------------------------------------------------+
+ ``Page Up``      | Page active browser window up                      |
+------------------+----------------------------------------------------+
+ ``Page Down``    | Page active browser window down                    |
+------------------+----------------------------------------------------+
+ ``Home``         | Page active browser window up                      |
+------------------+----------------------------------------------------+
+ ``End``          | Page active browser window down                    |
+------------------+----------------------------------------------------+
+ ``Left Arrow``   | Show next Image Viewer                             |
+------------------+----------------------------------------------------+
+ ``Right Arrow``  | View Next Image in Browser                         |
+------------------+----------------------------------------------------+
| ``Enter``        | Toggle Image Viewer (between hidden, showing and   |
|                  | fullscreen states)                                 |
+------------------+----------------------------------------------------+
| ``Escape``       | Hide Image Viewer                                  |
+------------------+----------------------------------------------------+
| **Image Viewer**                                                      |
+------------------+----------------------------------------------------+
| ``-`` (Minus)    | Zoom out                                           |
+------------------+----------------------------------------------------+
| ``+``            | Zoom in                                            |
+------------------+----------------------------------------------------+
| ``1``            | Zoom 100% (1 screen pixel = 1 image pixel)         |
+------------------+----------------------------------------------------+
| ``0`` or ``*``   | Fit to screen                                      |
+------------------+----------------------------------------------------+
| **Other**                                                             |
+------------------+----------------------------------------------------+
| ``\`` (Backslash)| Reverse image browser sort order                   |
+------------------+----------------------------------------------------+
| ``Delete``       | Delete selected images                             |
+------------------+----------------------------------------------------+
| F11              | Toggle application window fullscreen               |
+------------------+----------------------------------------------------+

*Next:* Learn about how picty handles photo `collections and the collections notebook <collections.rst>`_

Go back to the `index <index.rst>`_
