==================================
picty - A photo collection manager
==================================

picty is a photo manager designed around metadata and a lossless approach to image handling.

Key features:

* Supports big photo collections (20,000 plus images)
* Open more than one collection at a time and transfer images between them
* Collections are:

  - Folders of images in your local file system
  - Images on cameras, phones and other media devices
  - Photo hosting services (Flickr currently supported)

* picty does not "Import" photos into its own database, it simply provides an interface to accessing them wherever they are. picty does use a cache to keep track of the collection, however.

* Metadata support for the industry standards Exif, IPTC and Xmp
* Lossless approach:

  - picty writes all changes including image edits as metadata. e.g. an image crop is stored as any instruction, the original pixels remain in place
  - Nothing is written to images until you save your changes. Changes are stored between sessions in a cache file. Easily revert unsaved changes that you don't like.

* Basic image editing:

  - Current support for basic image enhancements such as brightness, contrast, cropping, rotation.
  - More tools coming soon (red eye reduction, levels, curves, noise reduction)

* Image tagging:

  - Use standard IPTC and Xmp keywords for image tags
  - Tag tree view to easily manage your tags and navigate your collection

* Folder view:

  - Navigate the directory heirarchy of your image collection

* Multi-monitor support

  - picty can takes advantage of the extra screen realestate.

* Customizable

  - Create launchers for external tools
  - Supports plugins - many of the current features (tagging and folder views, and all of the image editing tools) are provided by plugins

Get picty
----------

Nightly builds for Ubuntu are available at the launchpad ppa: https://launchpad.net/~damien-moore/+archive/ppa

Experimental Windows builds can be found at: http://sourceforge.net/projects/picty/files/

Or run from source...

Running picty from source
-------------------------

**Get the source**

::

  git clone https://github.com/spillz/picty

**Dependencies**

The python packages required to run picty are (available in most linux repos)::

    python (2.5 - 2.7)
    python-gtk2
    python-gnome2
    python-pyexiv2
    python-pyinotify

recommended packages::

    dcraw (basic raw processing support)
    totem (video thumbnailing)
    python-flickrapi (flickr collection support)
    python-osmgpsmap (geotagging support)

**Run picty**

Run the following commands in the terminal::

    cd <pictysourcedir>
    bin/picty

or see the INSTALL file for installation information. The benefits of installing are media support, desktop menus, and file manager integration (right click, open with picty for any image).

License Information
-------------------

`(c)` 2013 Damien Moore


License: GPL v3

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
