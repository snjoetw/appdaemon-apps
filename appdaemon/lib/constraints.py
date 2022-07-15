import calendar
import operator
from datetime import datetime, date

from lib.core.component import Component
from lib.helper import to_float, flatten_dict, is_float
from lib.schedule_job import has_scheduled_job


def get_constraint(app, config):
    platform = config['platform'];
    if platform == 'state':
        return StateConstraint(app, config)
    elif platform == 'triggered_state':
        return TriggeredStateConstraint(app, config)
    elif platform == 'triggered_event':
        return TriggeredEventConstraint(app, config)
    elif platform == 'triggered_action':
        return TriggeredActionConstraint(app, config)
    elif platform == 'triggered_time':
        return TriggeredTimeConstraint(app, config)
    elif platform == 'attribute':
        return AttributeConstraint(app, config)
    elif platform == 'time':
        return TimeConstraint(app, config)
    elif platform == 'has_scheduled_job':
        return HasScheduledJobConstraint(app, config)
    elif platform == 'day_of_week':
        return DayOfWeekConstraint(app, config)
    elif platform == 'template':
        return TemplateConstraint(app, config)
    elif platform == 'or':
        return OrConstraint(app, config)
    else:
        raise ValueError("Invalid constraint config: " + config)


def get_operator_fn(op):
    return {
        '<': operator.lt,
        '<=': operator.le,
        '>': operator.gt,
        '>=': operator.ge,
    }[op]


class Constraint(Component):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        raise NotImplementedError()

    def _matches_value(self, expected, actual):
        if isinstance(expected, list) and len(expected) == 1:
            expected = expected[0]

        if isinstance(expected, list):
            matched = actual in expected
            self.debug('Checking {} in {}? {}'.format(actual, expected, matched))
            return matched

        if not isinstance(expected, str):
            matched = expected == actual
            self.debug('Checking {} == {}? {}'.format(actual, expected, matched))
            return matched

        if not expected.startswith('<') and not expected.startswith('>'):
            matched = expected == actual
            self.debug('Checking {} == {}? {}'.format(actual, expected, matched))
            return matched

        if expected.startswith('<='):
            return self._matches_numeric_value('<=', expected, actual)
        elif expected.startswith('<'):
            return self._matches_numeric_value('<', expected, actual)
        elif expected.startswith('>='):
            return self._matches_numeric_value('>=', expected, actual)
        elif expected.startswith('>'):
            return self._matches_numeric_value('>', expected, actual)

        matched = expected == actual
        self.debug('Fallback, checking {} == {}? {}'.format(actual, expected, matched))
        return matched

    def _matches_numeric_value(self, op, expected, actual):
        expected = expected.replace(op, '')
        expected = to_float(expected)
        actual = to_float(actual) if is_float(actual) else None
        operator_fn = get_operator_fn(op)

        if actual is None:
            self.debug('Checking {} {} {}? {}'.format(actual, op, expected, False))
            return False

        matched = operator_fn(actual, expected)
        self.debug('Checking {} {} {}? {}'.format(actual, op, expected, matched))
        return matched


class StateConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        entity_ids = self.cfg.list('entity_id')
        state = self.cfg.value('state', None)
        negate = self.cfg.value('negate', False)
        match_all = self.cfg.value('match_all', False)
        last_changed_seconds = self.cfg.value('last_changed_seconds', None)
        return self._check_entity_state(entity_ids, state, negate, match_all, last_changed_seconds)

    def _check_entity_state(self, entity_ids, target_state, negate, match_all, last_changed_seconds):
        for entity_id in entity_ids:
            current_state = self.get_state(entity_id)
            if current_state is None:
                self.warn('Skipping ... current state is None for entity_id={}'.format(entity_id))
                return True

            condition = self._matches_value(target_state, current_state)

            if negate is True:
                condition = not condition

            if match_all and not condition:
                return False

            if condition and last_changed_seconds is not None:
                state_last_changed_in_sec = self.state_last_changed_duration(entity_id)
                condition = self._matches_value(last_changed_seconds, state_last_changed_in_sec)

            if not match_all and condition:
                self.debug('state constraint matched, entity_id={} '
                           'target_state={} '
                           'negate={}'.format(entity_id, target_state, negate))
                return condition

        if match_all:
            return True

        self.debug('no state constraint matched, entity_ids={} '
                   'target_state={} '
                   'negate={}'.format(entity_ids, target_state, negate))

        return False


class TemplateConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        expected_value = self.cfg.value('expected_value', None)
        actual_value = self.cfg.value('template', None)
        matched = self._matches_value(expected_value, actual_value)

        self.debug('Evaluating template={} with \n expected_value={} and \n actual_value={}, \n matching={}'.format(
            self.cfg.raw('template'),
            expected_value,
            actual_value,
            matched))

        return matched


class TriggeredStateConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        result = self.check_trigger_info(trigger_info)

        if self.cfg.value('negate', False):
            return not result

        return result

    def check_trigger_info(self, trigger_info):
        if trigger_info.platform != "state":
            return False

        triggered = trigger_info.data

        entity_id = self.cfg.list('entity_id', [])
        if entity_id and not self._matches_value(entity_id, triggered.get('entity_id')):
            return False

        attribute = self.cfg.list('attribute', [])
        if attribute and not self._matches_value(attribute, triggered.get('attribute')):
            return False

        from_state = self.cfg.list('from', [])
        if from_state and not self._matches_value(from_state, triggered.get('from')):
            return False

        to_state = self.cfg.list('to', [])
        if to_state and not self._matches_value(to_state, triggered.get('to')):
            return False

        return True


class TriggeredEventConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        if trigger_info.platform != "event":
            return False

        event = trigger_info.data
        result = self.check_event(event)
        if self.cfg.value('negate', False):
            return not result

        return result

    def check_event(self, event):
        entity_id = self.cfg.list('entity_id', [])
        if entity_id and event.get('entity_id') not in entity_id:
            return False

        event_name = self.cfg.list('event_name', [])
        if event_name and event.get('event_name') not in event_name:
            return False

        if not self.check_event_data(event.get('data', {})):
            return False

        return True

    def check_event_data(self, event_data):
        default = {}
        expected_event_data = flatten_dict(self.cfg.value("event_data", default))
        if not expected_event_data:
            return True

        event_data = flatten_dict(event_data)

        for key, expected in expected_event_data.items():
            actual = event_data.get(key)
            if not self._match_value(expected, actual):
                self.debug('Key={} has mismatched value => {} != {}'.format(key, expected, actual))
                return False

        return True

    @staticmethod
    def _match_value(expected, actual):
        if expected == actual:
            return True

        if isinstance(expected, list) and not isinstance(actual, list):
            return actual in expected

        return False


class TriggeredActionConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        if trigger_info.platform != 'action':
            return False

        action = trigger_info.data

        action_name = self.cfg.value('action_name', None)
        return action_name == action['action_name']


class TriggeredTimeConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        if trigger_info.platform != "time":
            return False

        triggered = trigger_info.data
        expected_times = self.cfg.list('time')
        matched = self._matches_value(expected_times, triggered['time'])

        self.debug('Checking {} matches {}? {}'.format(triggered['time'], expected_times, matched))

        return matched


class AttributeConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        entity_id = self.cfg.value('entity_id', None)
        attribute = self.cfg.value('attribute', None)
        value = self.cfg.value('value', None)
        negate = self.cfg.value('negate', False)
        current_value = self.get_state(entity_id, attribute=attribute)
        condition = self._matches_value(value, current_value)

        if negate is True:
            return not condition

        return condition


class TimeConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        start_time = self.cfg.value('start_time', None)
        end_time = self.cfg.value('end_time', None)

        if start_time and end_time:
            return self.app.now_is_between(start_time, end_time)

        start_time = self.get_state(self.cfg.value('start_time_entity_id', None))
        end_time = self.get_state(self.cfg.value('end_time_entity_id', None))

        if start_time and end_time:
            start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            return start_time <= datetime.now() < end_time


class HasScheduledJobConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        has_job = has_scheduled_job(self.app)
        negate = self.cfg.value('negate', False)

        if negate:
            return not has_job

        return has_job


class DayOfWeekConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)

    def check(self, trigger_info):
        days = self.cfg.list('day', [])
        today = date.today()
        day = calendar.day_name[today.weekday()]
        return day in days


class OrConstraint(Constraint):
    def __init__(self, app, constraint_config):
        super().__init__(app, constraint_config)
        self.constraints = []

        for config in self.cfg.list('constraints'):
            self.constraints.append(get_constraint(app, config))

    def check(self, trigger_info):
        for constraint in self.constraints:
            if constraint.check(trigger_info):
                return True
        return False
