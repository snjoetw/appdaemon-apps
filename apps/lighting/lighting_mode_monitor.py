from datetime import datetime, timedelta

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback
from lib.helper import to_int

PARTICIPATE_MIDNIGHT_TIME = 'participate_midnight_time'
PARTICIPATE_SLEEPING_TIME = 'participate_sleeping_time'
PARTICIPATE_SUNSET_TIME = 'participate_sunset_time'
MODE_ENTITY_ID = 'mode_entity_id'
LIGHT_SENSOR_ENTITY_ID = 'light_sensor_entity_id'
THRESHOLDS = 'thresholds'
EXCLUDE_ENTITY_IDS = 'exclude_entity_ids'

CHECK_FREQUENCY = 'check_frequency'
SLEEPING_TIME_ENTITY_ID = 'sleeping_time_entity_id'
MIDNIGHT_TIME_ENTITY_ID = 'midnight_time_entity_id'
LIGHTING_MODES = 'lighting_modes'


def _to_mode_config(mode):
    return {
        PARTICIPATE_MIDNIGHT_TIME: mode.get(PARTICIPATE_MIDNIGHT_TIME, False),
        PARTICIPATE_SLEEPING_TIME: mode.get(PARTICIPATE_SLEEPING_TIME, True),
        PARTICIPATE_SUNSET_TIME: mode.get(PARTICIPATE_SUNSET_TIME, True),
        MODE_ENTITY_ID: mode.get(MODE_ENTITY_ID),
        LIGHT_SENSOR_ENTITY_ID: mode.get(LIGHT_SENSOR_ENTITY_ID),
        CHECK_FREQUENCY: mode.get(CHECK_FREQUENCY, 60),
        THRESHOLDS: mode.get(THRESHOLDS),
        EXCLUDE_ENTITY_IDS: mode.get(EXCLUDE_ENTITY_IDS, [])
    }


def _check(app, config):
    mode_entity_id = config.get(MODE_ENTITY_ID)

    participate_midnight_time = config.get(PARTICIPATE_MIDNIGHT_TIME)
    if participate_midnight_time and app.is_midnight_time():
        app.set_mode_value(mode_entity_id, 'Midnight')
        return

    participate_sleeping_time = config.get(PARTICIPATE_SLEEPING_TIME)
    if participate_sleeping_time and app.is_sleeping_time():
        app.set_mode_value(mode_entity_id, 'Sleeping')
        return

    participate_sunset_time = config.get(PARTICIPATE_SUNSET_TIME)
    if participate_sunset_time and app.is_sunset_time():
        app.set_mode_value(mode_entity_id, 'Dark')
        return

    light_sensor_entity = app.get_state(config.get(LIGHT_SENSOR_ENTITY_ID), attribute='all')

    if light_sensor_entity is None:
        app.error('Unable to get light_sensor_entity={}'.format(config.get(LIGHT_SENSOR_ENTITY_ID)))
        return

    light_sensor_changed_at = light_sensor_entity['last_changed']

    excluded = config.get(EXCLUDE_ENTITY_IDS, [])
    if excluded is None:
        excluded = []

    for exclude in excluded:
        exclude_entity = app.get_state(exclude, attribute='all')

        if exclude_entity is None:
            app.error('Unable to get exclude entity with {}'.format(exclude))
            continue

        if exclude_entity['state'] == 'on':
            return
        # if darkness_entity was updated before exclude_entity, then skip
        elif light_sensor_changed_at < exclude_entity['last_changed']:
            return

    light_level = to_int(light_sensor_entity['state'], -1)

    if light_level == -1:
        app.warn('Unable to parse light level value: {}'.format(light_sensor_entity))
        return

    thresholds = config.get(THRESHOLDS)

    for threshold in sorted(thresholds, reverse=True):
        if light_level >= to_int(threshold):
            mode_value = thresholds[threshold]
            app.set_mode_value(mode_entity_id, mode_value)
            return


class LightingModeMonitor(BaseAutomation):
    def initialize(self):
        for mode in self.args.get(LIGHTING_MODES):
            config = _to_mode_config(mode)

            def run_every_handler_provider(_app, _config):
                @monitored_callback
                def run_every_handler(self, time=None, **kwargs):
                    _check(_app, _config)

                return run_every_handler

            now = datetime.now() + timedelta(seconds=2)
            self.run_every(run_every_handler_provider(self, config), now, config.get(CHECK_FREQUENCY))

            def state_change_handler_provider(_app, _config):
                def state_change_handler(self, entity_id, attribute, old, new,
                                         **kwargs):
                    _check(_app, _config)

                return state_change_handler

            self.listen_state(state_change_handler_provider(self, config),
                              config.get(LIGHT_SENSOR_ENTITY_ID))

    def is_midnight_time(self):
        return self.get_state(self.args.get(MIDNIGHT_TIME_ENTITY_ID)) == 'on'

    def is_sleeping_time(self):
        return self.get_state(self.args.get(SLEEPING_TIME_ENTITY_ID)) == 'on'

    def is_sunset_time(self):
        return self.sun_down()

    def set_mode_value(self, mode_entity_id, new_mode_value):
        current_mode_value = self.get_state(mode_entity_id)

        if current_mode_value != new_mode_value:
            self.log("Setting {} to {}".format(mode_entity_id, new_mode_value))
            self.select_option(mode_entity_id, new_mode_value)
