import concurrent
import time
import traceback
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


class BaseAutomation(hass.Hass):

    @property
    def cfg(self):
        return Config(self, self.args)

    @property
    def is_sleeping_time(self):
        sleeping_time_entity_id = self.cfg.value('sleeping_time_entity_id', 'binary_sensor.sleeping_time')
        return self.get_state(sleeping_time_entity_id) == 'on'

    @property
    def is_midnight_time(self):
        midnight_time_entity_id = self.cfg.value('midnight_time_entity_id', 'binary_sensor.midnight_time')
        return self.get_state(midnight_time_entity_id) == 'on'

    def debug(self, msg, *args):
        return self.log(msg, *args, level='DEBUG')

    def warn(self, msg, *args):
        return self.log(msg, *args, level='WARNING')

    def error(self, msg, *args):
        return self.log(msg, *args, level='ERROR')

    def sleep(self, duration):
        self.debug('About to sleep for {} sec'.format(duration))
        time.sleep(duration)

    def float_state(self, entity_id, default_value=None):
        return to_float(self.get_state(entity_id), default_value=default_value)

    def int_state(self, entity_id, default_value=None):
        return to_int(self.get_state(entity_id), default_value=default_value)

    def get_state(self, entity=None, **kwargs):
        if entity is None and not 'namespace' in kwargs:
            self.debug('About to retrieve state with entity=None\n{}'.format(''.join(traceback.format_stack())))

        return super().get_state(entity, **kwargs)

    def set_state(self, entity_id, **kwargs):
        return super().set_state(entity_id, **kwargs)

    def call_service(self, service, **kwargs):
        return super().call_service(service, **kwargs)

    def select_option(self, entity_id, option, **kwargs):
        if self.get_state(entity_id) == option:
            self.debug('{} already in {}, skipping ...'.format(entity_id, option))
            return

        options = self.get_state(entity_id, attribute='options')
        if option not in options:
            self.error('{} is not a valid option in {} ({})'.format(option, entity_id, options))
            return

        return super().select_option(entity_id, option, **kwargs)

    def cancel_timer(self, handle):
        try:
            if super().timer_running(handle):
                return super().cancel_timer(handle)
        except Exception as e:
            self.error('Error when cancel job, exception=%s: %s', e, traceback.format_exc())

    def do_actions(self, actions, trigger_info=None, do_parallel_actions=True):
        if len(actions) == 0:
            return

        if len(actions) == 1 or not do_parallel_actions:
            self.debug('About to do action(s) in sequential order')
            for action in actions:
                do_action(action, trigger_info)
            return

        self.debug('About to do action(s) in parallel')

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(do_action, action, trigger_info): action for action in actions}
            for future in concurrent.futures.as_completed(futures):
                future.result()

            self.debug('All action(s) are performed')

    def state_last_changed(self, entity_id, target_state=None):
        if target_state is not None and self.get_state(entity_id) != target_state:
            return None
        return to_datetime(self.get_state(entity_id, attribute='last_changed')) \
            .astimezone(self.AD.tz) \
            .replace(tzinfo=None)

    def state_last_changed_duration(self, entity_id, target_state=None):
        state_last_changed = self.state_last_changed(entity_id, target_state)
        if state_last_changed is None:
            return None
        delta = datetime.now() - state_last_changed
        return delta.total_seconds()


def do_action(action, trigger_info):
    if not action.check_action_constraints(trigger_info):
        return

    action.debug('About to do action: {}'.format(action))
    try:
        action.cfg.trigger_info = trigger_info
        return action.do_action(trigger_info)
    except Exception as e:
        action.error('Error when running actions in parallel: {}, action={}, trigger_info={}\n{}'.format(
            e,
            action,
            trigger_info,
            traceback.format_exc()))

    action.cfg.trigger_info = None
