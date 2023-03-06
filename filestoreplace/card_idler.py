import gevent
import gevent.monkey
gevent.monkey.patch_socket()
gevent.monkey.patch_select()
gevent.monkey.patch_ssl()

import os
import re
import sys
import math
import random
import logging
from io import open
from itertools import count
from contextlib import contextmanager
from collections import namedtuple
from steamctl.clients import CachingSteamClient
from steamctl.utils.web import make_requests_session
from steam.client import EMsg, EResult
from bs4 import BeautifulSoup

import steam.client.builtins.web
steam.client.builtins.web.make_requests_session = make_requests_session

LOG = logging.getLogger(__name__)


class IdleClient(CachingSteamClient):
    _LOG = logging.getLogger("IdleClient")

    def __init__(self, *args, **kwargs):
        CachingSteamClient.__init__(self, *args, **kwargs)

        self.wakeup = gevent.event.Event()
        self.newcards = gevent.event.Event()
        self.playing_blocked = gevent.event.Event()

        self.on(self.EVENT_DISCONNECTED, self.__handle_disconnected)
        self.on(self.EVENT_RECONNECT, self.__handle_reconnect)
        self.on(EMsg.ClientItemAnnouncements, self.__handle_item_notification)
        self.on(EMsg.ClientPlayingSessionState, self.__handle_playing_session)

    def connect(self, *args, **kwargs):
        self.wakeup.clear()
        self._LOG.info("Connecting to Steam...")
        return CachingSteamClient.connect(self, *args, **kwargs)

    def __handle_disconnected(self):
        self._LOG.info("Disconnected from Steam")
        self.wakeup.set()

    def __handle_reconnect(self, delay):
        if delay:
            self._LOG.info("Attemping reconnect in %s second(s)..", delay)

    def __handle_item_notification(self, msg):
        if msg.body.count_new_items == 100:
            self._LOG.info("Notification: over %s new items", msg.body.count_new_items)
        else:
            self._LOG.info("Notification: %s new item(s)", msg.body.count_new_items)
        self.newcards.set()
        self.wakeup.set()

    def __handle_playing_session(self, msg):
        if msg.body.playing_blocked:
            self.playing_blocked.set()
        else:
            self.playing_blocked.clear()
        self.wakeup.set()

@contextmanager
def init_client(args):
    s = IdleClient()
    s.login_from_args(args)
    yield s
    s.disconnect()


Game = namedtuple('Game', 'appid name cards_left playtime')


def cmd_assistant_idle_games(args):
    with init_client(args) as s:
        while True:
            #print('looping', s.connected, s.logged_on)
            # ensure we are connected and logged in
            if not s.connected:
                s.reconnect()
                continue

            if not s.logged_on:
                if not s.relogin_available:
                    return 1 # error

                result = s.relogin()

                if result != EResult.OK:
                    LOG.warning("Login failed: %s", repr(EResult(result)))

                continue

            s.wakeup.clear()

            # wait out any active sessions
            if s.playing_blocked.is_set():
                LOG.info("Another Steam session is playing right now. Waiting for it to finish...")
                s.wakeup.wait(timeout=3600)
                continue

            # check requested app ids against the license list
            app_ids = args.app_ids
            # TODO

            # idle games
            print("Playing game")
            s.games_played(app_ids)
            s.playing_blocked.wait(timeout=2)
            s.wakeup.clear()
            s.wakeup.wait(timeout=3)
            s.games_played([])
            s.sleep(1)
            s.disconnect()
            print("Disconnected")
            return

