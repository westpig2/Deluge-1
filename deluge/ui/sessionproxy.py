#
# sessionproxy.py
#
# Copyright (C) 2010 Andrew Resch <andrewresch@gmail.com>
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
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#
#

import logging
from twisted.internet.defer import inlineCallbacks, maybeDeferred, succeed, returnValue

import deluge.component as component
from deluge.ui.client import client
import time

log = logging.getLogger(__name__)

class SessionProxy(component.Component):
    """
    The SessionProxy component is used to cache session information client-side
    to reduce the number of RPCs needed to provide a rich user interface.

    On start-up it will query the Core for a full status of all the torrents in
    the session.  After that point, it will query the Core for only changes in
    the status of the torrents and will try to satisfy client requests from the
    cache.

    """
    def __init__(self):
        log.debug("SessionProxy init..")
        component.Component.__init__(self, "SessionProxy", interval=5)

        # Set the cache time in seconds
        # This is how long data will be valid before refetching from the core
        self.cache_time = 1.5

        # Hold the torrents' status.. {torrent_id: [time, {status_dict}], ...}
        self.torrents = {}

        # Holds the time of the last key update.. {torrent_id: {key1, time, ...}, ...}
        self.cache_times = {}

        client.register_event_handler(
            "TorrentStateChangedEvent", self.on_torrent_state_changed
        )
        client.register_event_handler(
            "TorrentRemovedEvent", self.on_torrent_removed
        )
        client.register_event_handler(
            "TorrentAddedEvent", self.on_torrent_added
        )

    def start(self):
        @inlineCallbacks
        def on_get_session_state(torrent_ids):
            for torrent_id in torrent_ids:
                # Let's at least store the torrent ids with empty statuses
                # so that upcomming queries don't throw errors.
                self.__on_torrents_status({torrent_id: {}})

            # Query for complete status in chunks
            for torrent_ids_chunk in self.__get_list_in_chunks(torrent_ids):
                chunk_status = yield client.core.get_torrents_status(
                    {'id': torrent_ids_chunk}, [], True
                )
                self.__on_torrents_status(chunk_status)
            returnValue(None)
        return client.core.get_session_state().addCallback(on_get_session_state)

    def stop(self):
        client.deregister_event_handler(
            "TorrentStateChangedEvent", self.on_torrent_state_changed
        )
        client.deregister_event_handler(
            "TorrentRemovedEvent", self.on_torrent_removed
        )
        client.deregister_event_handler(
            "TorrentAddedEvent", self.on_torrent_added
        )
        self.torrents = {}

    def create_status_dict(self, torrent_ids, keys):
        """
        Creates a status dict from the cache.

        :param torrent_ids: the torrent_ids
        :type torrent_ids: list of strings
        :param keys: the status keys
        :type keys: list of strings

        :returns: a dict with the status information for the *torrent_ids*
        :rtype: dict

        """
        sd = {}
        for torrent_id in torrent_ids:
            if keys:
                sd[torrent_id] = dict([
                    (x, y) for x, y in self.torrents[torrent_id][1].iteritems()
                    if x in keys
                ])
            else:
                sd[torrent_id] = dict(self.torrents[torrent_id][1])
        if len(torrent_ids) == 1:
            return sd[torrent_ids[0]]
        return sd

    def create_status_dict_from_deferred(self, result, torrent_ids, keys):
        if not torrent_ids:
            torrent_ids = result.keys()
        return self.create_status_dict(torrent_ids, keys)

    def get_torrent_status(self, torrent_id, keys):
        """
        Get a status dict for one torrent.

        :param torrent_id: the torrent_id
        :type torrent_id: string
        :param keys: the status keys
        :type keys: list of strings

        :returns: a dict of status information
        :rtype: dict

        """
        if torrent_id in self.torrents:
            # Keep track of keys we need to request from the core
            keys_to_get = []
            if not keys:
                keys = self.torrents[torrent_id][1].keys()

            for key in keys:
                if time.time() - self.cache_times[torrent_id][key] > self.cache_time:
                    keys_to_get.append(key)

            if not keys_to_get:
                return succeed(
                    self.create_status_dict([torrent_id], keys)[torrent_id]
                )
            else:
                d = client.core.get_torrent_status(
                    torrent_id, keys_to_get, True
                ).addCallback(self.__on_torrents_status, torrent_id)
                return d.addCallback(
                    self.create_status_dict_from_deferred,
                    [torrent_id],
                    keys
                )
        else:
            d = client.core.get_torrent_status(
                torrent_id, keys, True
            ).addCallback(self.__on_torrents_status, torrent_id)
            return d.addCallback(
                self.create_status_dict_from_deferred,
                None,
                keys
            )

    def get_torrents_status(self, filter_dict, keys):
        """
        Get a dict of torrent statuses.

        The filter can take 2 keys, *state* and *id*.  The state filter can be
        one of the torrent states or the special one *Active*.  The *id* key is
        simply a list of torrent_ids.

        :param filter_dict: the filter used for this query
        :type filter_dict: dict
        :param keys: the status keys
        :type keys: list of strings

        :returns: a dict of torrent_ids and their status dicts
        :rtype: dict

        """

        # Helper functions and callbacks ---------------------------------------
        def find_torrents_to_fetch(torrent_ids):
            to_fetch = []
            t = time.time()
            for torrent_id in torrent_ids:
                torrent = self.torrents[torrent_id]
                if t - torrent[0] > self.cache_time:
                    to_fetch.append(torrent_id)
                else:
                    # We need to check if a key is expired
                    for key in keys:
                        if t - self.cache_times[torrent_id].get(key, 0.0) > self.cache_time:
                            to_fetch.append(torrent_id)
                            break

            return to_fetch
        #-----------------------------------------------------------------------

        if not filter_dict:
            # This means we want all the torrents status
            # We get a list of any torrent_ids with expired status dicts
            to_fetch = find_torrents_to_fetch(self.torrents.keys())
            if to_fetch:
                for torrent_ids_chunk in self.__get_list_in_chunks(to_fetch):
                    d = client.core.get_torrents_status(
                        {"id": torrent_ids_chunk}, keys, True
                    ).addCallback(self.__on_torrents_status)
                return d.addCallback(
                    self.create_status_dict_from_deferred,
                    self.torrents.keys(),
                    keys
                )
            # Don't need to fetch anything
            return maybeDeferred(
                self.create_status_dict, self.torrents.keys(), keys
            )

        if len(filter_dict) == 1 and "id" in filter_dict:
            # At this point we should have a filter with just "id" in it
            to_fetch = find_torrents_to_fetch(filter_dict["id"])
            if to_fetch:
                for torrent_ids_chunk in self.__get_list_in_chunks(to_fetch):
                    d = client.core.get_torrents_status(
                        {"id": torrent_ids_chunk}, keys, True
                    ).addCallback(self.__on_torrents_status)
                return d.addCallback(
                    self.create_status_dict_from_deferred,
                    to_fetch,
                    keys
                )
            else:
                # Don't need to fetch anything, so just return data from the cache
                return maybeDeferred(
                    self.create_status_dict, filter_dict["id"], keys
                )
        else:
            # This is a keyworded filter so lets just pass it onto the core
            # XXX: Add more caching here.
            d = client.core.get_torrents_status(filter_dict, keys, True)
            d.addCallback(self.__on_torrents_status)
            return d.addCallback(
                self.create_status_dict_from_deferred,
                None,
                keys
            )

    def on_torrent_state_changed(self, torrent_id, state):
        if torrent_id in self.torrents:
            self.torrents[torrent_id][1]["state"] = state
            self.cache_times[torrent_id]["state"] = time.time()

    def on_torrent_added(self, torrent_id, from_state):
        self.torrents[torrent_id] = [time.time() - self.cache_time - 1, {}]
        self.cache_times[torrent_id] = {}
        def on_status(status):
            self.torrents[torrent_id][1].update(status)
            t = time.time()
            for key in status:
                self.cache_times[torrent_id][key] = t
        client.core.get_torrent_status(torrent_id, []).addCallback(on_status)

    def on_torrent_removed(self, torrent_id):
        del self.torrents[torrent_id]
        del self.cache_times[torrent_id]

    def __on_torrents_status(self, status, torrent_id=None):
        t = time.time()
        if torrent_id:
            status = {torrent_id: status}
        for key, value in status.items():
            self.torrents.setdefault(key, [t, value])
            self.torrents[key][0] = t
            self.torrents[key][1].update(value)
            for k in value:
                self.cache_times.setdefault(key, {}).update({k:t})
        return status

    def __get_list_in_chunks(self, list_to_chunk, chunk_size=30):
        """
        Yield successive n-sized chunks from list_to_chunk.
        """
        for i in xrange(0, len(list_to_chunk), chunk_size):
            yield list_to_chunk[i:i+chunk_size]
