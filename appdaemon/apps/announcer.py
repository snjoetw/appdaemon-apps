import concurrent
import traceback
from threading import Lock
from typing import List, Dict

from base_automation import BaseAutomation
from lib.annoucer.announcement import Announcement
from lib.annoucer.announcer_config import AnnouncerConfig
from lib.annoucer.media_manager import MediaManager
from lib.annoucer.player import Player
from lib.annoucer.player import create_player
from lib.core.monitored_callback import monitored_callback
from lib.helper import to_float


class Announcer(BaseAutomation):
    _volume_overrides: Dict
    _announcer_config: AnnouncerConfig
    _players: List[Player]
    _media_manager: MediaManager
    _queue: List
    _announcer_lock: Lock

    def initialize(self):
        self._announcer_config = AnnouncerConfig({
            'tts_platform': self.cfg.value('tts_platform'),
            'api_base_url': self.cfg.value('api_base_url'),
            'api_token': self.cfg.value('api_token'),
            'default_volume': self.cfg.value('default_volume'),
            'enabler_entity_id': self.cfg.value('enabler_entity_id'),
            'sleeping_time_entity_id': self.cfg.value('sleeping_time_entity_id'),
            'library_base_filepath': self.cfg.value('library_base_filepath'),
            'library_base_url_path': self.cfg.value('library_base_url_path'),
            'tts_base_filepath': self.cfg.value('tts_base_filepath'),
            'sound_path': self.cfg.value('sound_path'),
        })

        self._announcer_lock = Lock()
        self._queue = []
        self._volume_overrides = {}

        self._media_manager = MediaManager(self, self._announcer_config)
        self._players = [self._create_player(p) for p in self.cfg.value('players')]

        self.listen_state(self._sleeping_time_state_change_handler, self._announcer_config.sleeping_time_entity_id)

    def _create_player(self, raw_player_config):
        player_volume = raw_player_config.get('volume', {})
        raw_player_config['volume'] = {**self._announcer_config.default_volume, **player_volume}
        return create_player(self, raw_player_config, self._media_manager)

    @monitored_callback
    def _sleeping_time_state_change_handler(self, entity, attribute, old, new, kwargs):
        self._update_player_volumes()

    def _update_player_volumes(self):
        for player in self._players:
            for player_entity_id in player.player_entity_ids:
                volume_mode = self._figure_volume_mode(player_entity_id)
                overridden_volume = self._volume_overrides.get(player_entity_id, None)
                player.update_player_volume(player_entity_id, volume_mode, overridden_volume=overridden_volume)

    def get_default_player_volume(self, player_entity_id):
        for player in self._players:
            if player_entity_id in player.player_entity_ids:
                volume_mode = self._figure_volume_mode(player_entity_id)
                return player.get_default_volume(volume_mode)
        return None

    def _figure_volume_mode(self, player_entity_id):
        if self.get_state(self._announcer_config.sleeping_time_entity_id) == 'on':
            return 'sleeping'

        return 'regular'

    def override_volume(self, player_entity_id, volume):
        if volume is None:
            self._volume_overrides.pop(player_entity_id, None)
        else:
            self._volume_overrides[player_entity_id] = volume
        self._update_player_volumes()

    def enable_do_not_disturb(self, player_entity_id):
        self.override_volume(player_entity_id, 0)

    def disable_do_not_disturb(self, player_entity_id):
        self.override_volume(player_entity_id, None)

    def announce(self, message, use_cache=True, player_entity_ids=[], motion_entity_id=None, prelude_name=None):
        if self.get_state(self._announcer_config.enabler_entity_id) != 'on':
            self.log('Skipping ... announcer disable')
            return

        players = self._figure_players(player_entity_ids, motion_entity_id)
        if not players:
            self.error('Unable to find matching player with player_entity_ids={}, motion_entity_id={}'.format(
                player_entity_ids,
                motion_entity_id))
            return

        self.debug('Using players: {}'.format(players))

        self._queue.append(Announcement(message, use_cache, prelude_name, False, players))
        self._lock_and_announce()

    def _figure_players(self, player_entity_ids, motion_entity_id):
        self.debug('About to figure players player={}, motion={}'.format(player_entity_ids, motion_entity_id))

        if player_entity_ids:
            players = []

            for player in self._players:
                if not player.is_enabled:
                    self.debug('Player not enabled: {}'.format(player))
                    continue

                if all(id in player_entity_ids for id in player.player_entity_ids):
                    self.debug('Using {}'.format(player.player_entity_ids))
                    players.append(player)

            return players

        if motion_entity_id:
            for player in self._players:
                if motion_entity_id in player.motion_entity_ids:
                    self.debug('Using {}'.format(player))
                    return [player]
            return None

        return [p for p in self._players if not p.targeted_only and p.is_enabled]

    def _lock_and_announce(self):
        if not self._queue:
            self.debug('Nothing in the queue, skipping ...')
            return

        self.debug('About to acquire lock')
        self._announcer_lock.acquire()
        self.debug('Lock acquired')

        try:
            queue = self._dequeue_all()
            if not queue:
                self.debug('Nothing in the queue, skipping ....')
                return
        finally:
            self.debug('About to release lock')
            self._announcer_lock.release()
            self.debug('Lock released')

        self._do_announce(queue)

    def _do_announce(self, queue):
        if not queue:
            self.debug('Nothing in the queue, skipping ....')
            return

        previous_announcement = None
        player_announcements = {}

        while queue:
            announcement = queue.pop(0)
            if announcement == previous_announcement:
                self.debug('Skipping duplicate announcement: {}'.format(announcement))
                continue

            for player in announcement.players:
                if player not in player_announcements:
                    player_announcements[player] = []
                player_announcements[player].append(announcement)
            previous_announcement = announcement

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(player.play, announcements) for player, announcements in player_announcements.items()
            }

            try:
                for future in concurrent.futures.as_completed(futures):
                    future.result()
            except Exception as e:
                self.error('Error when calling announcer in parallel: {}, player_announcements={}\n{}'.format(
                    e,
                    player_announcements,
                    traceback.format_exc()))

    def _dequeue_all(self):
        dequeued, self._queue[:] = self._queue[:], []
        return dequeued
