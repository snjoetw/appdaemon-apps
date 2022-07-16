import time
from datetime import datetime

import appdaemon.plugins.hass.hassapi as hass

from lib.core.config import Config
from lib.helper import to_float, to_int, to_datetime

LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
}


class AsyncBaseAutomation(hass.Hass):

    @property
    def cfg(self):
        return Config(self, self.args)

    @property
    async def is_sleeping_time(self):
        sleeping_time_entity_id = self.cfg.value('sleeping_time_entity_id', 'binary_sensor.sleeping_time')
        return await self.get_state(sleeping_time_entity_id) == 'on'

    @property
    async def is_midnight_time(self):
        midnight_time_entity_id = self.cfg.value('midnight_time_entity_id', 'binary_sensor.midnight_time')
        return await self.get_state(midnight_time_entity_id) == 'on'

    def debug(self, msg, *args):
        return self.log(msg, *args, level='DEBUG')

    def warn(self, msg, *args):
        return self.log(msg, *args, level='WARNING')

    def error(self, msg, *args):
        return self.log(msg, *args, level='ERROR')

    def sleep(self, duration):
        self.debug('About to sleep for {} sec'.format(duration))
        time.sleep(duration)

    async def float_state(self, entity_id, default_value=None):
        return to_float(await self.get_state(entity_id), default_value=default_value)

    async def int_state(self, entity_id, default_value=None):
        return to_int(await self.get_state(entity_id), default_value=default_value)

    async def state(self, entity=None, **kwargs):
        return await super().get_state(entity, **kwargs)

    async def state_last_changed(self, entity_id, target_state=None):
        if target_state is not None and self.get_state(entity_id) != target_state:
            return None
        return to_datetime(await self.get_state(entity_id, attribute='last_changed')) \
            .astimezone(self.AD.tz) \
            .replace(tzinfo=None)

    async def state_last_changed_duration(self, entity_id, target_state=None):
        state_last_changed = self.state_last_changed(entity_id, target_state)
        if state_last_changed is None:
            return None
        delta = datetime.now() - state_last_changed
        return delta.total_seconds()
