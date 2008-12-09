#
# notification.py
#
# Copyright (C) 2008 Marcos Pinto ('markybob') <markybob@gmail.com>
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


import deluge.component as component
import deluge.common
import deluge.ui.gtkui.common as common
from deluge.log import LOG as log
from deluge.configmanager import ConfigManager
from deluge.ui.client import aclient as client

class Notification:
    def __init__(self):
        self.config = ConfigManager("gtkui.conf")
        self.tray = component.get("SystemTray")

    def notify(self, torrent_id):
        if self.config["ntf_tray_blink"]:
            self.tray.blink(True)
        if self.config["ntf_popup"] or self.config["ntf_email"]:
            self.get_torrent_status(torrent_id)

    def get_torrent_status(self, torrent_id):
        client.get_torrent_status(
            self._on_get_torrent_status, torrent_id, ["name", "num_files"])

    def _on_get_torrent_status(self, status):
        if status is None:
            return
        if self.config["ntf_popup"]:
            self.popup(status)
        if self.config["ntf_email"]:
            self.email(status)
        if self.config["ntf_sound"]:
            self.sound()

    def popup(self, status):
        """popups up notification of finished torrent"""
        if not deluge.common.windows_check():
            try:
                import pynotify
            except:
                log.warning("pynotify is not installed")
            else:
                if pynotify.init("Deluge"):
                    self.note = pynotify.Notification(_("Torrent complete"),
                        status["name"] + "\n" + _("Including %i files" % status["num_files"]))
                    self.note.set_icon_from_pixbuf(common.get_logo(48))
                    if not self.note.show():
                        log.warning("pynotify failed to show notification")

    def sound(self):
        """plays a sound when a torrent finishes"""
        try:
            import pygame
        except:
            log.warning("pygame is not installed")
        else:
            pygame.init()
            try:
                alert_sound = pygame.mixer.music
                alert_sound.load(self.config["ntf_sound_path"])
                alert_sound.play()
            except pygame.error, message:
                log.warning("pygame failed to play because %s" % (message))
            else:
                log.info("sound notification played successfully")

    def email(self, status):
        """sends email notification of finished torrent"""
        import smtplib
        headers = "From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % (
            self.config["ntf_email_add"], self.config["ntf_email_add"],
                "Finished torrent %s" % (status["name"]))
        text = _("This email is to inform you that Deluge has finished downloading %s , \
            which includes %i files.\nTo stop receiving these alerts, simply turn off \
            email notification in Deluge's preferences.\n\nThank you,\nDeluge")
        message = headers + text
        if self.config["ntf_security"] == 'SSL':
            port = 465
        elif self.config["ntf_security"] == 'TLS':
            port = 587
        elif self.config["ntf_security"] == None:
            port = 25
        mailServer = smtplib.SMTP(self.config["ntf_server"], port)
        if self.config["ntf_username"] and self.config["ntf_pass"]:
            if self.config["ntf_security"] == 'SSL' or 'TLS':
                mailServer.ehlo('x')
                mailServer.starttls()
                mailServer.ehlo('x')
            try:
                mailServer.login(self.config["ntf_username"], self.config["ntf_pass"])
            except smtplib.SMTPHeloError:
                log.warning("The server didn't reply properly to the helo greeting")
            except smtplib.SMTPAuthenticationError:
                log.warning("The server didn't accept the username/password combination")
        try:
            mailServer.sendmail(self.config["ntf_email_add"], self.config["ntf_email_add"], message)
            mailServer.quit()
        except:
            log.warning("sending email notification of finished torrent failed")
        else:
            log.info("sending email notification of finished torrent was successful")
