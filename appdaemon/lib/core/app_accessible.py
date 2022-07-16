from base_automation import BaseAutomation
from lib.helper import to_float, to_int


class AppAccessible:
    _app: BaseAutomation

    def __init__(self, app):
        self._app = app

    @property
    def app(self):
        return self._app

    def is_state_on(self, entity_id):
        state = self.get_state(entity_id)
        if entity_id.startswith('binary_sensor.'):
            return state == 'on'
        elif entity_id.startswith('lock.'):
            return state == 'unlocked'
        elif entity_id.startswith('cover.'):
            return state == 'open'

        raise ValueError("Unsupported entity_id={}".format(entity_id))

    def int_state(self, entity_id, **kwargs):
        return to_int(self.get_state(entity_id, **kwargs), -1)

    def float_state(self, entity_id):
        return to_float(self.get_state(entity_id))

    def get_state(self, entity=None, **kwargs):
        return self.app.get_state(entity, **kwargs)

    def set_state(self, entity_id, **kwargs):
        self.app.set_state(entity_id, **kwargs)

    def call_service(self, service, **kwargs):
        self.app.call_service(service, **kwargs)

    def select_option(self, entity_id, option, **kwargs):
        self.app.select_option(entity_id, option, **kwargs)

    def state_last_changed(self, entity_id, target_state=None):
        return self.app.state_last_changed(entity_id, target_state)

    def state_last_changed_duration(self, entity_id, target_state=None):
        return self.app.state_last_changed_duration(entity_id, target_state)

    def log(self, msg, *args, **kwargs):
        return self.app.log(msg, *args, **kwargs)

    def debug(self, msg, *args):
        return self.log(msg, *args, level='DEBUG')

    def warn(self, msg, *args):
        return self.log(msg, *args, level='WARNING')

    def error(self, msg, *args):
        return self.log(msg, *args, level='ERROR')

    @property
    def is_sleeping_time(self):
        return self.app.is_sleeping_time

    @property
    def is_midnight_time(self):
        return self.app.is_midnight_time
