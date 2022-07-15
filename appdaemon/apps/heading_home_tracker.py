from typing import List

from async_base_automation import AsyncBaseAutomation
from lib.presence_helper import PRESENCE_MODE_SOMEONE_IS_HOME, PERSON_STATUS_HOME, PERSON_STATUS_JUST_ARRIVED, \
    PERSON_STATUS_ARRIVING


class TrackerConfig:
    def __init__(self, name, presence_status_entity_id, proximity_entity_id, pronoun=None):
        self._name = name
        self._presence_status_entity_id = presence_status_entity_id
        self._proximity_entity_id = proximity_entity_id
        self._pronoun = pronoun

    @property
    def name(self):
        return self._name

    @property
    def presence_status_entity_id(self):
        return self._presence_status_entity_id

    @property
    def proximity_entity_id(self):
        return self._proximity_entity_id

    @property
    def pronoun(self):
        return self._pronoun


class HeadingHomeTracker(AsyncBaseAutomation):
    car_tracker_configs: List[TrackerConfig]
    person_tracker_configs: List[TrackerConfig]
    presence_mode_entity_id: str

    async def initialize(self):
        self.car_tracker_configs = [TrackerConfig(**car) for car in self.cfg.list('car_trackers')]
        self.person_tracker_configs = [TrackerConfig(**person) for person in self.cfg.list('person_trackers')]
        self.presence_mode_entity_id = self.cfg.value('presence_mode_entity_id')

        for tracker in self.car_tracker_configs + self.person_tracker_configs:
            self.listen_state(self._presence_status_change_handler, tracker.presence_status_entity_id)

    async def _presence_status_change_handler(self, entity_id, attribute, old, new, kwargs):
        self.log('Presence status changed, entity_id=%s, attribute=%s, old=%s, new=%s', entity_id, attribute, old, new)

        presence_mode = await self.state(self.presence_mode_entity_id)
        if presence_mode != PRESENCE_MODE_SOMEONE_IS_HOME:
            return

        message = await self.figure_person_heading_home_message(entity_id)
        self.log(message)

    async def figure_person_heading_home_message(self, entity_id):
        person = await self.figure_person_heading_home(entity_id)
        if not person:
            return

        current_presence_status = await self.state(entity_id)
        if current_presence_status == PERSON_STATUS_JUST_ARRIVED:
            return "{} just arrived home.".format(person.name)
        elif current_presence_status != PERSON_STATUS_ARRIVING:
            return

        proximity = await self.int_state(person.proximity_entity_id)
        if proximity > 0:
            return "{} is heading home, {} is about {} km away.".format(person.name, person.pronoun, proximity)
        else:
            return "{} is heading home.".format(person.name, proximity)

    async def figure_person_heading_home(self, entity_id):
        if entity_id in [e.presence_status_entity_id for e in self.car_tracker_configs]:
            for config in self.person_tracker_configs:
                presence_status = await self.state(config.presence_status_entity_id)
                if presence_status != PERSON_STATUS_HOME:
                    self.debug('Triggered by car tracker (%s) and found %s is not home', entity_id, config.name)
                    return config
        elif entity_id in [e.presence_status_entity_id for e in self.person_tracker_configs]:
            for config in self.person_tracker_configs:
                if config.presence_status_entity_id == entity_id:
                    self.debug('Triggered by person tracker (%s, %s)', entity_id, config.name)
                    return config

        self.log('Could not determine which person is heading home, entity_id=%s', entity_id)
        return None
