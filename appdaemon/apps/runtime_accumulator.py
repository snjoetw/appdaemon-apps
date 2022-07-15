from datetime import datetime, timedelta
from enum import Enum

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback
from lib.helper import to_float

ACCUMULATOR_CACHE = {}


def createAccumulator(app, config):
    app.debug(config)
    type = AccumulatorType[config.get('accumulator_type', 'DEFAULT')]

    if type in ACCUMULATOR_CACHE:
        return ACCUMULATOR_CACHE[type]

    if type == AccumulatorType.WATTAGE:
        return WattageAccumulator(app, config)
    elif type == AccumulatorType.STATE_VALUE:
        return StateValueAccumulator(app, config)
    elif type == AccumulatorType.TESLA:
        ACCUMULATOR_CACHE[type] = TeslaChargingAccumulator(app, config)
        return ACCUMULATOR_CACHE[type]
    else:
        return EntityStateAccumulator(app, config)


class RuntimeAccumulator(BaseAutomation):
    def initialize(self):
        self._reset_start_time = self.args['reset_start_time']
        self._reset_end_time = self.args['reset_end_time']
        self._accumulator_configs = self.args['accumulators']
        self._accessor = ValueAccessor(self)

        now = datetime.now() + timedelta(seconds=2)
        self._handle = self.run_every(self._run_every_handler, now, 60)

    @monitored_callback
    def _run_every_handler(self, time=None, **kwargs):
        for config in self._accumulator_configs:
            if self._should_reset():
                self._accessor.set_runtime(config['accumulate_entity_id'], 0)

            original_value = self._accessor.get_runtime(
                config['accumulate_entity_id'])
            accumulator = createAccumulator(self, {
                **config,
                'original_value': original_value
            })

            is_running = accumulator.is_running()
            self.debug('Checking with {}, is_running={}'.format(accumulator,
                                                                is_running))

            if is_running:
                self._accessor.set_runtime(config['accumulate_entity_id'],
                                           accumulator.accumulate())

    def _should_reset(self):
        return self.now_is_between(self._reset_start_time,
                                   self._reset_end_time)


class AccumulatorType(Enum):
    DEFAULT = 0
    WATTAGE = 1
    STATE_VALUE = 2
    TESLA = 3


class Accumulator:

    def __init__(self, app, config):
        self._app = app
        self._accumulate_entity_id = config['accumulate_entity_id']

    def is_running(self):
        raise NotImplementedError

    def accumulate_step(self):
        raise NotImplementedError

    def accumulate(self):
        return self._original_value + self.accumulate_step()

    def __repr__(self):
        return "{}(accumulate_entity_id={})".format(
            self.__class__.__name__,
            self._accumulate_entity_id)


class EntityStateAccumulator(Accumulator):

    def __init__(self, app, config):
        super().__init__(app, config)
        self._accumulate_step = to_float(config.get('step', 1))
        self._always_running = config.get('always_running', False)
        self._original_value = config['original_value']

        if not self._always_running:
            self._target_entity_id = config['target_entity_id']
            self._target_attribute = config.get('target_attribute')
            self._running_state_value = config.get('running_state_value')
            self._running_attribute_value = config.get(
                'running_attribute_value')

    def is_running(self):
        if self._always_running:
            return True

        target_entity = self._app.get_state(self._target_entity_id,
                                            attribute='all')

        self._app.debug('target_entity: {}'.format(target_entity))

        if target_entity is None:
            return False

        if self._running_state_value:
            if target_entity['state'] != self._running_state_value:
                return False

        if self._running_attribute_value:
            value = target_entity['attributes'].get(self._target_attribute)
            if value != self._running_attribute_value:
                return False

        return True

    def accumulate_step(self):
        return self._accumulate_step


class WattageAccumulator(EntityStateAccumulator):

    def __init__(self, app, config):
        super().__init__(app, config)

        self._wattage_entity_id = config.get('wattage_entity_id')
        self._wattage = config.get('wattage')

    def accumulate_step(self):
        wattage = self._wattage

        if self._wattage_entity_id:
            wattage = to_float(self._app.get_state(self._wattage_entity_id))

        # kilo-watt * 1min/60min
        return wattage / 1000 / 60


class StateValueAccumulator(EntityStateAccumulator):

    def __init__(self, app, config):
        super().__init__(app, config)

        self._target_entity_id = config['target_entity_id']

    def accumulate_step(self):
        return to_float(self._app.get_state(self._target_entity_id), 0)


class TeslaChargingAccumulator(Accumulator):

    def __init__(self, app, config):
        super().__init__(app, config)
        self._location_home_name = config['location_home_name']
        self._charging_state_name = config['charging_state_name']

        self._charging_state_entity_id = config['charging_state_entity_id']
        self._location_entity_id = config['location_entity_id']
        self._charge_energy_added_entity_id = config[
            'charge_energy_added_entity_id']
        self._original_value = config['original_value']

        self._previous_state = None

    def is_running(self):
        current_location = self._app.get_state(self._location_entity_id)

        self._app.debug('current_location={} location_home_name={}'.format(
            current_location, self._location_home_name))

        if current_location != self._location_home_name:
            return False

        current_state = self._app.get_state(self._charging_state_entity_id)

        self._app.debug(
            'current_state={} charging_state_name={}'.format(current_state,
                                                             self._charging_state_name))
        if not current_state:
            return False

        was_charging = self._previous_state == self._charging_state_name
        is_still_charging = current_state == self._charging_state_name

        # update previous state to current
        self._previous_state = current_state

        self._app.debug(
            'was_charging={} is_still_charging={} is_running={}'.format(
                was_charging,
                is_still_charging,
                was_charging and not is_still_charging))

        return was_charging and not is_still_charging

    def accumulate_step(self):
        return to_float(
            self._app.get_state(self._charge_energy_added_entity_id), 0)


class ValueAccessor:
    def __init__(self, app):
        self._app = app

    def get_runtime(self, accumulate_entity_id):
        value = self._app.get_state(accumulate_entity_id)
        if value is None:
            return 0
        return to_float(value)

    def set_runtime(self, accumulate_entity_id, value):
        original = self.get_runtime(accumulate_entity_id)

        if original != value:
            self._app.debug(
                'Setting {} from {} to {}'.format(accumulate_entity_id,
                                                  original, value))
            self._app.set_state(accumulate_entity_id, state=value)
