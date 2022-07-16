from base_automation import BaseAutomation
from lib.core.app_accessible import AppAccessible
from lib.core.config import Config
from lib.time_wrapper import NowWrapper


class Component(AppAccessible):
    _app: BaseAutomation
    _config: Config

    def __init__(self, app, config):
        super().__init__(app)
        self._config = Config(app, config)

    @property
    def cfg(self):
        return self._config

    @property
    def now(self):
        return NowWrapper(self.app)

    @property
    def is_sleeping_time(self):
        sleeping_time_entity_id = self.cfg.value('sleeping_time_entity_id', 'binary_sensor.sleeping_time')
        return self.get_state(sleeping_time_entity_id) == 'on'

    @property
    def is_midnight_time(self):
        midnight_time_entity_id = self.cfg.value('midnight_time_entity_id', 'binary_sensor.midnight_time')
        return self.get_state(midnight_time_entity_id) == 'on'

    @property
    def is_sun_down(self):
        return self.app.sun_down()

    def __repr__(self):
        return "{}(config={})".format(
            self.__class__.__name__,
            self._config)
