Installation
============

You have two options for running picty: install from binary packages, or download and run the source directly. The windows version lacks some of the features of the linux version.

Binary Packages
---------------

Unstable, testing releases are available for

 * Windows users: sourceforge hosted binaries at
   http://sourceforge.net/projects/picty/files

 * Ubuntu users: install the picty PPA following the directions at
   http://launchpad.net/~damien-moore/+archive/ppa

Running from Source
-------------------

*Windows*

You will need to download:

 * Python 2.7 from www.python.org
 * PyGtk 2.0 all-in-one installer from http://www.pygtk.org/downloads.html
 * pyexiv2 installer from http://tilloy.net/dev/pyexiv2/download.html (make sure you get the python 2.7 version)
 * Bazaar Version Control Sytem: http://wiki.bazaar.canonical.com/Download
 * Optional: osmgpsmap (for GPS mapping plugin to work)
 * Optional: flickrapi (for flickr support)

Open a terminal (Start menu -> Run -> Cmd.exe) and type::

    cd <directory to locate picty>
    bzr branch lp:picty
    cd picty
    c:\python27\python bin\picty


*Ubuntu and other Debian Based Linux System*

To install the required dependencies, open a linux terminal and type::

    sudo apt-get install bzr python-pyinotify python-pyexiv2 python-gtk2 python-gnome2 dcraw python-osmgpsmap python-flickrapi

(*bzr* is to get the code, and *dcraw*, *python-osmgpsmap* and *python-flickrapi* are optional)

To get the code::

    cd <directory to locate picty>
    bzr branch lp:picty

To run::

    cd picty
    bin/picty

To update to the latest version::

    cd picty
    bzr pull

You can also install the program into the system, which means picty will show up in your system application menus and be registered as a handler for cameras and image files -- see the INSTALL file

*Other Linux*

The basic instructions for Ubuntu and other Debian based systems apply except that you won't be using apt-get to install the packages and the packages may be named slightly differently.

Running picty for the First Time
================================

Most users will want to manage a collection of photos that are already
present in their file system, so the following steps will walk you through
the steps to do that. Note that during this process picty is not going to
alter your images or the directory structure in any way, so it should be
perfectly safe to test picty on your photo collection.

1. When you run picty for the first time you will be greeted with the
   following window:

   .. image:: screenshots/start.png

2. Click on the button labeled ``New Collection`` and you will see the
   following dialog:

   .. image:: screenshots/new-collection.png

   On the left side of the dialog you will see a list of the collection types
   that picty supports and "Local Store" should be selected. This is the default
   collection type and the one you should use for a local photo collection.

3. You need to give the collection a name, and specify the directory path
   to your images. I have used the name ``main`` and the path
   ``/home/damien/Pictures``. Press the "..." button to use the system folder
   picker to specify the image path.

   .. image:: screenshots/new-collection-details.png

4. There are also a number of advanced options that you can change, but the
   defaults should work fine for most users. These are discussed in more detail
   in the `collections <collections.rst>`_ topic.

5. Now click on the button labeled ``Create`` to create your collection.
   (The create button will be disabled unless you enter a valid name and
   folder for the collection.)

   As soon as the collection is created
   picty is going to scan the image folder and (by default) all
   of its subfolders for photos and videos. Then picty will then generate a
   thumbnail and read a subset of its metadata (tags and other information
   embedded in the image file). Depending on how many images you have in
   your collection, this could take some time, especially the first run. picty
   stores the information about the collection in a cache file so that
   loading the collection should be very fast after this initial scan has
   been completed.

   If all has gone well, the main window should display a grid
   of image thumbnails in a notepage like the following:

   .. image:: screenshots/new-collection-created.png

   As the scan continues, new images will be added to this page.

   You should notice that while the scan is going on the app remains (mostly) responsive.
   You can view and edit images while the scan continues in the background.


*Next:* Learn about picty's `user interface <user_interface.rst>`_

Or go back to the `index <index.rst>`_
