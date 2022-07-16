import re
from datetime import datetime
from enum import Enum
from typing import List

from configurable_automation import ConfigurableAutomation
from lib.actions import Action
from lib.core.component import Component
from lib.helper import to_float, to_datetime

CHECKER_RESULT_CACHE = {}


class Checker(Component):

    def __init__(self, app, config):
        super().__init__(app, config)

    def check(self):
        raise NotImplementedError()


class DeviceResult:
    def __init__(self, entity_id, result_type, metadata={}):
        self._entity_id = entity_id
        self._result_type = result_type
        self._metadata = metadata

    @property
    def result_type(self):
        return self._result_type

    @property
    def is_ok(self):
        return self.result_type == ResultType.OK or self.result_type == ResultType.IGNORE

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def metadata(self):
        return self._metadata

    def __repr__(self):
        return '{}(result_type={}, is_ok={}, entity_id={})'.format(
            self.__class__.__name__,
            self.result_type,
            self.is_ok,
            self.entity_id)


class DeviceMonitor(ConfigurableAutomation):

    def initialize(self):
        super().initialize()

        self.init_trigger('time', {
            'seconds': 900,
        })

        self.init_handler(self.create_handler(
            [],
            [WrapperAction(self, self.args)]))

    def get_checker_result(self, checker_type):
        return CHECKER_RESULT_CACHE.get(checker_type)


class WrapperAction(Action):
    checkers: List[Checker]

    def __init__(self, app, action_config):
        super().__init__(app, action_config)

        self.checkers = [create_checker(app, c) for c in self.cfg.list('checkers', None)]

    def do_action(self, trigger_info):
        for checker in self.checkers:
            result = checker.check()
            notification_id = checker.__class__.__name__.lower()

            self._update_result_cache(checker, result)

            if result.error_message:
                self.call_service(
                    'persistent_notification/create', **{
                        'notification_id': notification_id,
                        'message': result.error_message
                    })
            else:
                self.call_service(
                    'persistent_notification/dismiss', **{
                        'notification_id': notification_id,
                    })

    def _update_result_cache(self, checker: Checker, checker_result: DeviceResult):
        checker_type = checker.cfg.value('type')
        CHECKER_RESULT_CACHE[checker_type] = checker_result


def create_checker(app, config):
    type = config['type']
    if type == 'vent':
        return VentChecker(app, config)
    elif type == 'battery_level':
        return BatteryLevelChecker(app, config)
    elif type == 'unavailable_entity':
        return UnavailableEntityChecker(app, config)
    elif type == 'ge_bulb':
        return GEBulbChecker(app, config)
    elif type == 'ping':
        return PingChecker(app, config)

    raise ValueError('Invalid action config: {}'.format(config))


class EntityNameFilteringChecker(Checker):
    def __init__(self, app, config):
        super().__init__(app, config)
        self._patterns = self.cfg.list('pattern', None)

    def check(self):
        self.debug('Checking with {} and pattern={}'.format(type(self).__name__, self._patterns))

        device_results = []
        checked_entity_ids = []
        all_entities = self.app.get_state().items()

        for pattern_config in self._patterns:
            (pattern, config) = self._extract_config(pattern_config)

            for entity_id, entity in all_entities:
                if entity_id is None or entity is None:
                    continue

                if entity_id in checked_entity_ids:
                    continue

                if re.search(pattern, entity_id):
                    result = self._check_entity(entity, config)
                    checked_entity_ids.append(entity_id)

                    self.debug('Checked entity_id={} with result={}'.format(entity_id, result))

                    if not result.is_ok:
                        device_results.append(result)

        if not device_results:
            return CheckerResult(device_results, None)

        return CheckerResult(device_results, self._get_message(device_results))

    def _extract_config(self, config):
        if isinstance(config, str):
            return (config, {})

        pattern = config['pattern']
        return (pattern, config)

    def _check_entity(self, entity, config):
        raise NotImplementedError()

    def _get_message(self, results):
        raise NotImplementedError()


class VentChecker(EntityNameFilteringChecker):
    def __init__(self, app, config):
        super().__init__(app, config)

    def _check_entity(self, entity, config):
        threshold_in_min = config.get('threshold_in_min', 120)

        entity_id = entity['entity_id']
        state = entity['state']
        last_updated = entity.get('last_updated')

        if state == 'unavailable':
            return error(entity_id, ResultType.UNAVAILABLE)

        if last_updated is None:
            return error(entity_id, ResultType.ATTRIBUTE_MISSING)

        last_updated = to_datetime(last_updated).replace(tzinfo=None)
        difference = datetime.utcnow() - last_updated
        difference_in_min = difference.total_seconds() / 60

        if difference_in_min > threshold_in_min:
            return error(entity_id, ResultType.LOST_CONNECTION)

        # current_position = entity.get("attributes", {}).get("current_position")
        # is_opened = entity['state'] == "open"
        #
        # if current_position is None:
        #     self._open_vent(entity_id)
        # elif current_position >= 5 and not is_opened:
        #     self._open_vent(entity_id)

        return ok(entity_id)

    def _open_vent(self, entity_id):
        self.call_service("cover/open_cover", entity_id=entity_id)

    def _close_vent(self, entity_id):
        self.call_service("cover/close_cover", entity_id=entity_id)

    def _get_message(self, results):
        def get_item_message(device_result):
            friendly_name = self.app.get_state(device_result.entity_id, attribute='friendly_name')
            return '{}'.format(friendly_name)

        return create_error_message(
            results,
            'Found issue with following vents:\n',
            get_item_message
        )


class GEBulbChecker(EntityNameFilteringChecker):
    def __init__(self, app, config):
        super().__init__(app, config)

    def _check_entity(self, entity, config):
        entity_id = entity['entity_id']
        return error(entity_id, ResultType.INTRUDING_DEVICE)

    def _get_message(self, results):
        def get_item_message(device_result):
            return '{}'.format(device_result.entity_id)

        return create_error_message(
            results,
            'Following GE bulbs are connected:\n',
            get_item_message
        )


class UnavailableEntityChecker(EntityNameFilteringChecker):

    def __init__(self, app, config):
        super().__init__(app, config)

    def _check_entity(self, entity, config):
        entity_id = entity['entity_id']
        if config.get('ignore', False):
            return ignore(entity_id)

        state = entity['state']

        if state in ('unavailable', 'dead'):
            return error(entity_id, ResultType.UNAVAILABLE)

        return ok(entity_id)

    def _get_message(self, results):
        def get_item_message(device_result):
            friendly_name = self.app.get_state(device_result.entity_id, attribute='friendly_name')
            return '{} ({})'.format(friendly_name, device_result.entity_id)

        return create_error_message(
            results,
            'Following entities are unavailable:\n',
            get_item_message
        )


class BatteryLevelChecker(EntityNameFilteringChecker):
    def __init__(self, app, config):
        super().__init__(app, config)

    def _check_entity(self, entity, config):
        entity_id = entity['entity_id']
        if config.get('ignore', False):
            return ignore(entity_id)

        battery_level = self._get_entity_battery_level(entity)
        if battery_level is None:
            return ignore(entity_id)

        threshold = config.get('battery_level_threshold', 15)
        if battery_level > threshold:
            return ok(entity_id)

        return error(entity_id, ResultType.LOW_BATTERY, {
            'battery_level': battery_level,
        })

    def _get_message(self, results):
        def get_item_message(device_result):
            battery_level = device_result.metadata.get('battery_level')
            return '{} ({}%)'.format(device_result.entity_id, battery_level)

        return create_error_message(
            results,
            'Following entities are low in battery:\n',
            get_item_message
        )

    def _get_entity_battery_level(self, entity):
        if entity['entity_id'].endswith('battery') or entity['entity_id'].endswith('battery_level'):
            state = entity['state']
            if state is None or state in ['unknown', 'unavailable', '']:
                return None

            return to_float(state)

        attributes = entity.get("attributes", {})
        return to_float(attributes.get("battery_level"))


class PingChecker(EntityNameFilteringChecker):
    def __init__(self, app, config):
        super().__init__(app, config)

        self._threshold = config.get('threshold', 120)

    def _check_entity(self, entity, config):
        entity_id = entity['entity_id']
        if config.get('ignore', False):
            return ignore(entity_id)

        ping_ms = to_float(entity['state'], -1)

        if ping_ms < 0:
            return ignore(entity_id)

        if ping_ms < self._threshold:
            return ok(entity_id)

        return error(entity_id, ResultType.NETWORK_ISSUE)

    def _get_message(self, results):
        def get_item_message(device_result):
            return '{}'.format(device_result.entity_id)

        return create_error_message(
            results,
            'Following entities are having networking issue:\n',
            get_item_message
        )


def ok(entity_id):
    return DeviceResult(entity_id, ResultType.OK)


def ignore(entity_id):
    return DeviceResult(entity_id, ResultType.IGNORE)


def error(entity_id, result_type, metadata={}):
    return DeviceResult(entity_id, result_type, metadata)


def create_error_message(device_results, main_message, item_message_provider):
    message = main_message
    for device_result in device_results:
        if device_result.is_ok:
            continue

        message += '* {}\n'.format(item_message_provider(device_result))
    return message


class ResultType(Enum):
    OK = 1
    IGNORE = 2
    ENTITY_NOT_FOUND = 3
    ATTRIBUTE_MISSING = 4
    LOST_CONNECTION = 5
    INTRUDING_DEVICE = 6
    LOW_BATTERY = 7
    UNAVAILABLE = 8
    NETWORK_ISSUE = 9


class CheckerResult:
    def __init__(self, device_results, error_message):
        self._device_results = device_results
        self._error_device_results = [r for r in device_results if not r.is_ok]
        self._error_message = error_message

    @property
    def has_error_device_result(self):
        return len(self._error_device_results) > 0

    @property
    def error_device_results(self):
        return self._error_device_results

    @property
    def error_message(self):
        return self._error_message
