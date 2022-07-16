from threading import Lock

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback
from lib.helper import to_int
from lib.presence_helper import PERSON_STATUS_HOME, \
    PERSON_STATUS_JUST_ARRIVED, \
    PERSON_STATUS_ARRIVING, \
    PERSON_STATUS_JUST_LEFT, \
    PERSON_STATUS_AWAY

HOME_ZONE = "home"


class PresenceStatusAutomation(BaseAutomation):
    def initialize(self):
        self._lock = Lock()
        self._config = {}
        self._state_change_handles = {}

        for attributes in self.cfg.value("device_entity_ids"):
            presence_entity_id = next(iter(attributes))
            config = attributes[presence_entity_id]
            status_entity_id = config["status_entity_id"]
            proximity_entity_id = config["proximity_entity_id"]

            self._config[presence_entity_id] = {
                "status_entity_id": status_entity_id,
                "proximity_entity_id": proximity_entity_id,
                'proximity_toward_count': 0
            }

            self.listen_state(self.presence_change_handler, presence_entity_id)

            self.listen_state(self.proximity_change_handler,
                              proximity_entity_id,
                              attribute="all",
                              presence_entity_id=presence_entity_id)

            current_state = self.get_state(presence_entity_id)
            if current_state == HOME_ZONE:
                self.select_option(status_entity_id, PERSON_STATUS_HOME)
            else:
                self.select_option(status_entity_id, PERSON_STATUS_AWAY)

    @monitored_callback
    def presence_change_handler(self, entity, attribute, old, new, kwargs):
        self._lock.acquire()

        try:
            if old != HOME_ZONE and new == HOME_ZONE:
                status_entity_id = self._config[entity]["status_entity_id"]
                self.select_option(status_entity_id, PERSON_STATUS_JUST_ARRIVED)
                self.schedule_entity_state_changer(entity, PERSON_STATUS_JUST_ARRIVED)
                self.log("{} just arrived home".format(self.friendly_name(status_entity_id)))
            elif old == HOME_ZONE and new != HOME_ZONE:
                status_entity_id = self._config[entity]["status_entity_id"]
                self.select_option(status_entity_id, PERSON_STATUS_JUST_LEFT)
                self.schedule_entity_state_changer(entity, PERSON_STATUS_JUST_LEFT)
                self.log("{} just left home".format(self.friendly_name(status_entity_id)))
        finally:
            self._lock.release()

    def update_status_state(self, kwargs):
        self._lock.acquire()

        try:
            device_entity_id = kwargs["device_entity_id"]
            status_entity_id = self._config[device_entity_id]["status_entity_id"]
            previous_state = kwargs["previous_state"]

            if previous_state == PERSON_STATUS_JUST_ARRIVED:
                self.select_option(status_entity_id, PERSON_STATUS_HOME)
                self.log("{} is now home".format(self.friendly_name(status_entity_id)))
            elif previous_state == PERSON_STATUS_JUST_LEFT:
                self.select_option(status_entity_id, PERSON_STATUS_AWAY)
                self.log("{} is now away".format(self.friendly_name(status_entity_id)))
        finally:
            self._lock.release()

    def schedule_entity_state_changer(self, device_entity_id, previous_state):
        self.cancel_timer(self._state_change_handles.get(device_entity_id))
        self._state_change_handles[device_entity_id] = self.run_in(
            self.update_status_state,
            10 * 60,
            device_entity_id=device_entity_id,
            previous_state=previous_state)

    @monitored_callback
    def proximity_change_handler(self, entity, attribute, old, new, kwargs):
        self._lock.acquire()

        try:
            self.log('Proximity change, entity={}, new={}'.format(entity, new))

            presence_entity_id = kwargs['presence_entity_id']
            config = self._config.get(presence_entity_id)
            status_entity_id = config.get('status_entity_id')
            current_status = self.get_state(status_entity_id)

            if current_status != PERSON_STATUS_AWAY and current_status != PERSON_STATUS_ARRIVING:
                self.log('Current status ({}) is not away or arriving'.format(current_status))

                config['proximity_toward_count'] = 0
                return

            is_heading_home = self.is_heading_home(config, new)

            if is_heading_home:
                self.select_option(status_entity_id, PERSON_STATUS_ARRIVING)
            elif current_status == PERSON_STATUS_ARRIVING:
                self.select_option(status_entity_id, PERSON_STATUS_AWAY)
        finally:
            self._lock.release()

    def is_heading_home(self, config, proximity):
        dir_of_travel = proximity.get('attributes', {}).get('dir_of_travel')
        if dir_of_travel != 'towards' and dir_of_travel != 'stationary':
            self.log('Direction is not towards home: {}'.format(dir_of_travel))

            config['proximity_toward_count'] = 0
            return False

        config['proximity_toward_count'] += 1
        if config['proximity_toward_count'] < 3:
            self.log('Is heading home but not confident enough: {}'.format(config['proximity_toward_count']))
            return False

        distance = to_int(proximity.get('state'), -1)
        if distance < 0 or distance >= 5:
            self.log('Is heading home but still too far away: {}'.format(distance))
            return False

        self.log('Is heading home now')

        return True
