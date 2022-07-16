from typing import List

from async_base_automation import AsyncBaseAutomation
from lib.core.config import Config
from lib.helper import OCCUPANCY_UNKNOWN, OCCUPANCY_OCCUPIED, OCCUPANCY_UNOCCUPIED, STATE_ON, STATE_OFF, STATE_PLAYING


class RoomConfig:
    def __init__(self, config: Config):
        self._name = config.value('name')
        self._occupancy_entity_id = config.value('occupancy_entity_id')
        self._entry_entity_ids = config.list('entry_entity_id')
        self._movement_entity_ids = config.list('movement_entity_id')
        self._media_player_entity_id = config.value('media_player_entity_id')

    @property
    def name(self):
        return self._name

    @property
    def occupancy_entity_id(self):
        return self._occupancy_entity_id

    @property
    def entry_entity_ids(self):
        return self._entry_entity_ids

    @property
    def movement_entity_ids(self):
        return self._movement_entity_ids

    @property
    def media_player_entity_id(self):
        return self._media_player_entity_id


class OccupancyMonitor(AsyncBaseAutomation):
    room_configs: List[RoomConfig]

    async def initialize(self):
        self.room_configs = [RoomConfig(Config(self, room)) for room in self.cfg.list('rooms')]
        for room_config in self.room_configs:
            for entity_id in room_config.entry_entity_ids:
                self.listen_state(self._entry_state_change_handler, entity_id)
            for entity_id in room_config.movement_entity_ids:
                self.listen_state(self._movement_state_change_handler, entity_id)

    async def _entry_state_change_handler(self, entity_id, attribute, old, new, kwargs):
        room_config = await self.figure_room_with_entry_state_change(entity_id)
        if not room_config:
            self.warn('Entry state changed by entity_id=%s but could not find room config', entity_id)
            return

        if new == STATE_ON:
            await self.select_option(room_config.occupancy_entity_id, OCCUPANCY_UNKNOWN)
        elif new == STATE_OFF:
            if room_config.media_player_entity_id:
                is_media_playing = await self.state(room_config.media_player_entity_id) == STATE_PLAYING
                if is_media_playing:
                    await self.select_option(room_config.occupancy_entity_id, OCCUPANCY_OCCUPIED)
                else:
                    await self.select_option(room_config.occupancy_entity_id, OCCUPANCY_UNOCCUPIED)
            else:
                await self.select_option(room_config.occupancy_entity_id, OCCUPANCY_UNOCCUPIED)

    async def _movement_state_change_handler(self, entity_id, attribute, old, new, kwargs):
        if new != STATE_ON:
            return

        room_config = await self.figure_room_with_movement_state_change(entity_id)
        if not room_config:
            self.warn('Movement state changed by entity_id=%s but could not find room config', entity_id)
            return

        for entry_entity_id in room_config.entry_entity_ids:
            entry_entity_state = await self.state(entry_entity_id)
            if entry_entity_state != STATE_OFF:
                return

        await self.select_option(room_config.occupancy_entity_id, OCCUPANCY_OCCUPIED)

    async def figure_room_with_entry_state_change(self, entry_entity_id) -> RoomConfig:
        for room_config in self.room_configs:
            for entity_id in room_config.entry_entity_ids:
                if entity_id == entry_entity_id:
                    return room_config
        return None

    async def figure_room_with_movement_state_change(self, movement_entity_id) -> RoomConfig:
        for room_config in self.room_configs:
            for entity_id in room_config.movement_entity_ids:
                if entity_id == movement_entity_id:
                    return room_config
        return None

    async def select_option(self, entity_id, option, **kwargs):
        self.log('Selecting %s with %s', entity_id, option)
