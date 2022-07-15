from datetime import datetime
from enum import Enum
from random import randint

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback

PRESENCE_MODE_ENTITY_ID = 'presence_mode_entity_id'
SCHEDULED_JOB_HANDLES = {}


class ActionType(Enum):
    TURN_ON = 'turn_on'
    TURN_OFF = 'turn_off'


def _do_action(app, action_type, light_entity_id):
    app.log('About to {} {}'.format(action_type, light_entity_id))

    if action_type == ActionType.TURN_ON:
        app.turn_on(light_entity_id)
    elif action_type == ActionType.TURN_OFF:
        app.turn_off(light_entity_id)


class VacantLightSimulator(BaseAutomation):
    def initialize(self):
        self._check_frequency = 60
        self._configs = [SimulatorConfig(c) for c in self.cfg.value('simulators')]

        presence_mode_entity_id = self.cfg.value('presence_mode_entity_id')
        self.listen_state(self._presence_mode_change_handler, presence_mode_entity_id, immediate=True)

    @monitored_callback
    def _presence_mode_change_handler(self, entity, attribute, old, new, kwargs):
        if new != 'No One is Home':
            for handle in SCHEDULED_JOB_HANDLES.values():
                self.cancel_timer(handle)
            SCHEDULED_JOB_HANDLES.clear()

            self.log('Presence mode is {}, simulators deactivated, {}'.format(new, SCHEDULED_JOB_HANDLES))
        else:
            if 'main' in SCHEDULED_JOB_HANDLES:
                return

            SCHEDULED_JOB_HANDLES['main'] = self.run_every(self._run_every_handler, datetime.now(),
                                                           self._check_frequency)

            self.log('Presence mode is {}, simulators activated, {}'.format(new, SCHEDULED_JOB_HANDLES))

    def _run_every_handler(self, time=None, **kwargs):
        for config in self._configs:
            if not self._should_schedule_jobs(config):
                continue

            if not self._has_scheduled_jobs(config.id):
                self._schedule_jobs(config)

    def _should_schedule_jobs(self, config):
        if config.light_mode_entity_id is not None:
            light_mode_state = self.get_state(config.light_mode_entity_id)

            if light_mode_state not in config.light_mode_states:
                return False

        if config.start_time and config.end_time:
            return self.now_is_between(config.start_time, config.end_time)

        return True

    def _has_scheduled_jobs(self, job_name):
        for key in SCHEDULED_JOB_HANDLES.keys():
            if key.startswith(job_name):
                return True

        return False

    def _schedule_jobs(self, config):
        turn_on_delay = randint(config.turn_on_min_delay, config.turn_on_max_delay)
        self._schedule_job(config, ActionType.TURN_ON, turn_on_delay)

        turn_off_delay = turn_on_delay + randint(config.turn_off_min_delay, config.turn_off_max_delay)
        self._schedule_job(config, ActionType.TURN_OFF, turn_off_delay)

    def _schedule_job(self, config, action_type, delay):
        handle = self.run_in(self._job_runner, delay, action_type=action_type, config=config)

        job_name = self._job_name(config, action_type)
        SCHEDULED_JOB_HANDLES[job_name] = handle

        self.log('Scheduled job to run in {} seconds, job_name={}'.format(delay, job_name))

    def _job_runner(self, kwargs={}):
        action_type = kwargs.get('action_type')
        config = kwargs.get('config')
        _do_action(self, action_type, config.light_entity_id)

        job_name = self._job_name(config, action_type)
        del SCHEDULED_JOB_HANDLES[job_name]

        self.log('Finished running {}'.format(job_name))

    def _job_name(self, config, action_type):
        return '{}_{}'.format(config.id, action_type)


class SimulatorConfig:
    def __init__(self, config):
        self._turn_on_min_delay = config.get('turn_on_min_delay', 3600)
        self._turn_on_max_delay = config.get('turn_on_max_delay', 5400)
        self._turn_off_min_delay = config.get('turn_off_min_delay', 1800)
        self._turn_off_max_delay = config.get('turn_off_max_delay', 2700)
        self._light_entity_id = config.get('light_entity_id')

        self._light_mode_entity_id = config.get('light_mode_entity_id')
        self._light_mode_states = config.get('light_mode_states', [])

        self._start_time = config.get('start_time')
        self._end_time = config.get('end_time')

    @property
    def id(self):
        return self._light_entity_id

    @property
    def turn_on_min_delay(self):
        return self._turn_on_min_delay

    @property
    def turn_on_max_delay(self):
        return self._turn_on_max_delay

    @property
    def turn_off_min_delay(self):
        return self._turn_off_min_delay

    @property
    def turn_off_max_delay(self):
        return self._turn_off_max_delay

    @property
    def light_entity_id(self):
        return self._light_entity_id

    @property
    def light_mode_entity_id(self):
        return self._light_mode_entity_id

    @property
    def light_mode_states(self):
        return self._light_mode_states

    @property
    def start_time(self):
        return self._start_time

    @property
    def end_time(self):
        return self._end_time
