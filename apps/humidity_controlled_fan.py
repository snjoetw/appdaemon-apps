from typing import List

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback
from lib.schedule_job import schedule_turn_on_job


class HumidityControlledFan(BaseAutomation):
    _fan_entity_id: str
    _trigger_entity_id: str
    _trigger_from_states: List
    _trigger_to_states: List
    _humidity_entity_id: str
    target_humidity_diff_in_percent: int
    _before_trigger_humidity: float
    _max_allowed_humidity: float
    max_fan_runtime_in_min: int
    turn_on_fan_delay_in_min: int

    def initialize(self):
        self._fan_entity_id = self.cfg.value('fan_entity_id', required=True)
        self._trigger_entity_id = self.cfg.value('trigger_entity_id', required=True)
        self._trigger_from_states = self.cfg.list('trigger_from_states')
        self._trigger_to_states = self.cfg.list('trigger_to_states')
        self._humidity_entity_id = self.cfg.value('humidity_entity_id', required=True)
        self.target_humidity_diff_in_percent = self.cfg.int('target_humidity_diff_in_percent', 5)
        self._max_allowed_humidity = self.cfg.float('max_allowed_humidity', 55)
        self.max_fan_runtime_in_min = self.cfg.int('max_fan_runtime_in_min', 120)
        self.turn_on_fan_delay_in_min = self.cfg.int('turn_on_fan_delay_in_min', 10)
        self._before_trigger_humidity = None

        self.listen_state(self._trigger_state_change_handler, self._trigger_entity_id)
        self.listen_state(self._humidity_change_handler, self._humidity_entity_id)

    @monitored_callback
    def _trigger_state_change_handler(self, entity, attribute, old, new, kwargs):
        if old == new:
            return

        if old in self._trigger_from_states and new in self._trigger_to_states:
            self._before_trigger_humidity = self._figure_before_trigger_humidity()
            self.debug('About to trigger, saving before_trigger_humidity as %s', self._before_trigger_humidity)
        elif old in self._trigger_to_states and new in self._trigger_from_states:
            self.debug('Finished triggering, scheduled turn-on-fan job in %s min', self.turn_on_fan_delay_in_min)
            schedule_turn_on_job(self, self.turn_on_fan_delay_in_min * 60, self._fan_entity_id)

    def _figure_before_trigger_humidity(self):
        before_trigger_humidity = self.float_state(self._humidity_entity_id)
        if before_trigger_humidity > self._max_allowed_humidity:
            before_trigger_humidity = self._max_allowed_humidity
        return before_trigger_humidity

    @monitored_callback
    def _humidity_change_handler(self, entity, attribute, old, new, kwargs):
        fan_on_duration = self.state_last_changed_duration(self._fan_entity_id, 'on')
        if fan_on_duration is None:
            self.debug('Fan is not on, skipping')
            return

        if fan_on_duration / 60 > self.max_fan_runtime_in_min:
            self.debug('Fan turned-on for more than %s min (%s min), turning fan off now', self.max_fan_runtime_in_min,
                       fan_on_duration)
            self._turn_off_fan()
            return

        if self._before_trigger_humidity is None:
            self.debug('No saved before_trigger_humidity, skipping')
            return

        current_humidity = self.float_state(self._humidity_entity_id)
        diff = (current_humidity - self._before_trigger_humidity) / self._before_trigger_humidity * 100

        if diff >= self.target_humidity_diff_in_percent:
            self.debug('Current humidity (%s) is still too high (diff=%s%), skipping', current_humidity, diff)
            return

        if self.get_state(self._trigger_entity_id) == 'on':
            self.debug('Trigger entity (%s) is still on, skipping', self._trigger_entity_id)
            return

        self.debug('Current humidity (%s) is within target (diff=%s%), turning fan off now', current_humidity, diff)
        self._turn_off_fan()

    def _turn_off_fan(self):
        self._before_trigger_humidity = None
        self.turn_off(self._fan_entity_id)
