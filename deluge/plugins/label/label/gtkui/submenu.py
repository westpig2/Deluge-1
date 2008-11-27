#
# blocklist/gtkui.py
#
# Copyright (C) 2007 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2008 Mark Stahler ('kramed') <markstahler@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA    02110-1301, USA.
#


import os
import pkg_resources    # access plugin egg
from deluge.log import LOG as log
from deluge import component    # for systray
import ui
import gtk, gobject
from deluge.ui.client import aclient

from deluge.configmanager import ConfigManager
config  = ConfigManager("label.conf")
NO_LABEL = "No Label"

class LabelMenu(gtk.MenuItem):
    def __init__(self):
        gtk.MenuItem.__init__(self, _("Label"))

        self.sub_menu = gtk.Menu()
        self.set_submenu(self.sub_menu)
        self.items = []

        #attach..
        torrentmenu = component.get("MenuBar").torrentmenu
        self.sub_menu.connect("show", self.on_show, None)
        aclient.connect_on_new_core(self._on_new_core)


    def _on_new_core(self, data = None):
        self.on_show()

    def get_torrent_ids(self):
        return component.get("TorrentView").get_selected_torrents()


    def on_show(self, widget=None, data=None):
        log.debug("label-on-show")
        aclient.label_get_labels(self.cb_labels)
        aclient.force_call(block=True)

    def cb_labels(self , labels):
        for child in self.sub_menu.get_children():
            self.sub_menu.remove(child)
        for label in [NO_LABEL] + labels:
            item = gtk.MenuItem(label.replace("_","__"))
            item.connect("activate", self.on_select_label, label)
            self.sub_menu.append(item)
        self.show_all()

    def on_select_label(self, widget=None, label_id = None):
        log.debug("select label:%s,%s" % (label_id ,self.get_torrent_ids()) )
        for torrent_id in self.get_torrent_ids():
            aclient.label_set_torrent(None, torrent_id, label_id)
        #aclient.force_call(block=True)