from datetime import datetime
from enum import Enum

from base_automation import BaseAutomation
from lib.core.app_accessible import AppAccessible
from lib.core.component import Component
from lib.core.monitored_callback import monitored_callback


class DarknessLevel(Enum):
    UNKNOWN = 'Unknown'
    DARK = 'Dark'
    NOT_DARK = 'Not Dark'


class Zone(Component):
    def __init__(self, app, config):
        super().__init__(app, {})

        self._darkness_entity_id = config['darkness_entity_id']
        self._areas = [Area(app, a) for a in config['areas']]
        self._participate_sun_down_time = config.get('participate_sun_down_time')
        self._previous_darkness_level = DarknessLevel.UNKNOWN
        self._darkness_level_changed_at = None
        self._min_check_frequency_in_min = config.get('min_check_frequency_in_min', 5)

        monitored_entity_ids = set()
        for area in self._areas:
            monitored_entity_ids.update(area.monitored_entity_ids)

        for entity_id in monitored_entity_ids:
            self.app.listen_state(self._state_change_handler, entity_id)

    def log(self, msg, level="INFO"):
        msg = self._darkness_entity_id + ': ' + msg
        return super().log(msg, level=level)

    @monitored_callback
    def _state_change_handler(self, entity, attribute, old, new, kwargs):
        darkness_level = self._determine_darkness()

        if darkness_level == self._previous_darkness_level:
            return

        # update the changed time to now so we won't check for another 5 min
        self._darkness_level_changed_at = datetime.now()
        self._previous_darkness_level = darkness_level

        self.debug('Current darkness level: {}'.format(darkness_level))

        if darkness_level is DarknessLevel.UNKNOWN:
            return

        self.select_option(self._darkness_entity_id, darkness_level.value)

    def _determine_darkness(self):
        if not self._should_check_darkness_level():
            return self._previous_darkness_level

        if self._participate_sun_down_time and self.is_sun_down:
            self.debug('In sun down time')
            return DarknessLevel.DARK

        areas = [area for area in self._areas if area.can_determine_darkness()]
        if not areas:
            self.debug('None of the area can check darkness')
            return DarknessLevel.UNKNOWN

        dark_count = 0
        not_dark_count = 0

        for area in areas:
            if area.determine_darkness() == DarknessLevel.DARK:
                dark_count += 1
            else:
                not_dark_count += 1

        self.debug('Dark ({}) v.s. Not Dark ({})'.format(dark_count, not_dark_count))

        if not_dark_count > dark_count:
            return DarknessLevel.NOT_DARK

        return DarknessLevel.DARK

    def _should_check_darkness_level(self):
        if self._darkness_level_changed_at is None:
            return True

        if self._previous_darkness_level is DarknessLevel.UNKNOWN:
            return True

        if self._min_check_frequency_in_min <= 0:
            return True

        time_diff = datetime.now() - self._darkness_level_changed_at
        time_diff_in_min = time_diff.total_seconds() / 60
        if time_diff_in_min > self._min_check_frequency_in_min:
            return True

        self.debug('Last darkness level change is within {} min, skipping...'.format(self._min_check_frequency_in_min))

        return False


class Area(AppAccessible):
    def __init__(self, app, config):
        super().__init__(app)
        self._light_sensor_entity_id = config['light_sensor_entity_id']
        self._darkness_threshold = config['darkness_threshold']
        self._skip_when_on_entity_ids = config.get('skip_when_on_entity_ids', [])

    @property
    def monitored_entity_ids(self):
        return [self._light_sensor_entity_id] + self._skip_when_on_entity_ids

    def can_determine_darkness(self):
        if self.get_state(self._light_sensor_entity_id) == 'unavailable':
            return False

        if not self._skip_when_on_entity_ids:
            return True

        for entity_id in self._skip_when_on_entity_ids:
            state = self.get_state(entity_id)
            if state == 'on':
                return False

        return True

    def determine_darkness(self):
        light_level = self.float_state(self._light_sensor_entity_id)

        if light_level is None:
            self.warn('Light level is None')
            return DarknessLevel.UNKNOWN

        if light_level > self._darkness_threshold:
            return DarknessLevel.NOT_DARK

        return DarknessLevel.DARK


class DarknessMonitor(BaseAutomation):
    def initialize(self):
        self._zones = [Zone(self, c) for c in self.cfg.value('zones')]
        pass
