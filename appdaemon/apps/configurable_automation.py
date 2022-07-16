import concurrent
import traceback
from datetime import datetime
from typing import List, Any

from base_automation import BaseAutomation, do_action
from lib.actions import get_action
from lib.constraints import get_constraint
from lib.core.app_accessible import AppAccessible
from lib.core.monitored_callback import monitored_callback
from lib.triggers import get_trigger


class ConfigurableAutomation(BaseAutomation):
    _throttle_in_seconds: int
    _last_run: datetime
    _handlers: List[Any]
    _global_constraints: List[Any]

    def initialize(self):
        self._global_constraints = []
        self._handlers = []
        self._last_run = None
        self._throttle_in_seconds = self.args.get("throttle_in_seconds")

    def init_trigger(self, platform, config):
        config['platform'] = platform
        get_trigger(self, config, self.trigger_handler)

    def init_global_constraint(self, platform, config):
        constraint = self.create_constraint(platform, config)
        self._global_constraints.append(constraint)

    def create_constraint(self, platform, config):
        config['platform'] = platform
        return get_constraint(self, config)

    def create_action(self, platform, config):
        config['platform'] = platform
        return get_action(self, config)

    def init_handler(self, handler):
        self._handlers.append(handler)

    def create_handler(self, constraints, actions, do_parallel_actions=True):
        return Handler(self, constraints, actions, do_parallel_actions=do_parallel_actions)

    def trigger_handler(self, trigger_info):
        self.log('Triggered with trigger_info={}'.format(trigger_info))

        try:
            for constraint in self._global_constraints:
                if not constraint.check(trigger_info):
                    return

            for handler in self._handlers:
                if handler.check_constraints(trigger_info):
                    if self.should_throttle():
                        self.log('Skipping ... action throttled, last_run={}, throttle_in_seconds={}'.format(
                            self._last_run,
                            self._throttle_in_seconds))
                        return

                    handler.do_actions(trigger_info)
                    self._last_run = datetime.now()
                    return
        except Exception as e:
            self.error('Error when handling trigger: ' + traceback.format_exc())

    def should_throttle(self):
        if self._throttle_in_seconds is None or self._last_run is None:
            return False

        diff_in_seconds = (datetime.now() - self._last_run).total_seconds()
        return diff_in_seconds < self._throttle_in_seconds


class Handler(AppAccessible):
    def __init__(self, app, constraints, actions, do_parallel_actions=True):
        super().__init__(app)

        self._do_parallel_actions = do_parallel_actions
        self._constraints = constraints
        self._actions = actions

    def check_constraints(self, trigger_info):
        self.debug('Checking handler={}'.format(self))
        if self._constraints:
            for constraint in self._constraints:
                constraint.cfg.trigger_info = trigger_info
                matched = constraint.check(trigger_info)
                constraint.cfg.trigger_info = None

                if not matched:
                    self.debug('Constraint does not match {}'.format(constraint))
                    return False

        self.debug('All constraints match')
        return True

    @monitored_callback
    def do_actions(self, trigger_info):
        if len(self._actions) == 0:
            return

        if len(self._actions) == 1 or not self._do_parallel_actions:
            self.debug('About to do action(s) in sequential order')
            for action in self._actions:
                do_action(action, trigger_info)
            return

        self.debug('About to do action(s) in parallel')
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(do_action, action, trigger_info): action for action in self._actions}
            for future in concurrent.futures.as_completed(futures):
                future.result()

            self.debug('All action(s) are performed')

    def __repr__(self):
        return "{}(constraints={}, actions={}, do_parallel_actions={})".format(
            self.__class__.__name__,
            self._constraints,
            self._actions,
            self._do_parallel_actions)
