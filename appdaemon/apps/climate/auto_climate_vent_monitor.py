from base_automation import BaseAutomation
from datetime import datetime, timedelta

from lib.actions import set_cover_position
from lib.core.monitored_callback import monitored_callback
from lib.helper import to_float


class AutoClimateVentMonitor(BaseAutomation):
    def initialize(self):
        self.enabler_entity_id = self.cfg.value('enabler_entity_id')
        self.climate_entity_id = self.cfg.value('climate_entity_id')
        self.climat_target_temp_high = self.cfg.value('target_temp_high')
        self.climat_target_temp_low = self.cfg.value('target_temp_low')
        self.hvac_action_entity_id = self.cfg.value('hvac_action_entity_id')
        self.last_hvac_action_entity_id = self.cfg.value('last_hvac_action_entity_id')
        self.zone_configs = [ZoneConfig(z) for z in self.cfg.list('zones')]

        self.listen_state(self.temperature_change_handler, self.climate_entity_id, attribute="all")

        for config in self.zone_configs:
            self.listen_state(self.temperature_change_handler, config.temperature_entity_id)

        now = datetime.now() + timedelta(seconds=2)
        self.run_every(self.run_every_handler, now, 60)

    @monitored_callback
    def temperature_change_handler(self, entity, attribute, old, new, kwargs):
        self.adjust_vent_openness()

    @monitored_callback
    def run_every_handler(self, kwargs):
        self.adjust_vent_openness()

    def adjust_vent_openness(self):
        if self.get_state(self.enabler_entity_id) != 'on':
            self.debug('Skipping ... not enabled')
            return

        if self.get_state(self.climate_entity_id, attribute='hold_mode') == 'vacation':
            self.debug('Skipping ... vacation mode')
            return

        if self.get_state(self.hvac_action_entity_id) not in ('heating', 'cooling'):
            self.debug('Skipping ... hvac not running')
            return

        for config in self.zone_configs:
            current = self.float_state(config.temperature_entity_id)
            target = self.target_temperature()

            if current is None or target is None:
                self.warn('Skipping ... current={} or target={} is None for {}'.format(current, target,
                                                                                       config.temperature_entity_id))
                continue

            adjusted_current = self.adjusted_current_temperature(target, current, config)
            open_percent = self.calculate_open_percent(target, adjusted_current, config)
            open_position = round(open_percent * 100)
            # round to nearest 10
            open_position = round(open_position / 10) * 10

            for vent_entity_id in config.vent_entity_ids:
                set_cover_position(self, vent_entity_id, open_position, config.position_difference_threshold)

    def target_temperature(self):
        target = self.get_state(self.climate_entity_id, attribute='temperature')
        # if single temp mode
        if target is not None:
            return to_float(target)

        # if high & low temp mode
        if self.is_heating_mode():
            target = self.get_state(self.climat_target_temp_low)
        else:
            target = self.get_state(self.climat_target_temp_high)

        return to_float(target)

    def adjusted_current_temperature(self, target, current, zone_config):
        """
        :rtype: float returns adjust temperature that's bounded by offset high and low
        """
        target_offset_high = self.target_offset_high(zone_config)
        target_offset_low = self.target_offset_low(zone_config)

        if current > target + target_offset_high:
            current = target + target_offset_high
        elif current < target + target_offset_low:
            current = target + target_offset_low

        return current

    def target_offset_high(self, zone_config):
        return zone_config.heating_temp_offset_high if self.is_heating_mode() else zone_config.cooling_temp_offset_high

    def target_offset_low(self, zone_config):
        return zone_config.heating_temp_offset_low if self.is_heating_mode() else zone_config.cooling_temp_offset_low

    def target_offset_scale(self, zone_config):
        return 1 / (self.target_offset_high(zone_config) - self.target_offset_low(zone_config))

    def calculate_open_percent(self, target, adjusted_current, zone_config):
        if zone_config.fully_open_entity_id and self.get_state(zone_config.fully_open_entity_id) == 'on':
            self.debug('fully_open_entity state is on, open vent to 100%')
            return 1

        if self.is_heating_mode():
            target_high = target + self.target_offset_high(zone_config)
            open_percent = round((target_high - adjusted_current) * self.target_offset_scale(zone_config), 1)
            self.debug('Calculating open_percent for heating, adjusted_current={}, target_high={}, '
                       'target_offset_scale={}, open_percent={}'.format(adjusted_current,
                                                                        target_high,
                                                                        self.target_offset_scale(zone_config),
                                                                        open_percent))

        else:
            target_low = target + self.target_offset_low(zone_config)
            open_percent = round((adjusted_current - target_low) * self.target_offset_scale(zone_config), 1)
            self.debug('Calculating open_percent for cooling, adjusted_current={}, target_low={}, '
                       'target_offset_scale={}, open_percent={}'.format(adjusted_current,
                                                                        target_low,
                                                                        self.target_offset_scale(zone_config),
                                                                        open_percent))

        if open_percent < zone_config.min_open_percent:
            open_percent = zone_config.min_open_percent
            self.debug('Overrode open_percent to {}'.format(open_percent))

        return open_percent

    def is_heating_mode(self):
        hvac_action = self.get_state(self.last_hvac_action_entity_id)
        return hvac_action == 'heating'


class ZoneConfig:
    def __init__(self, config):
        self._temperature_entity_id = config.get("temperature_entity_id")
        self._vent_entity_ids = config.get("vent_entity_ids")
        self._cooling_temp_offset_high = config.get("cooling_temp_offset_high")
        self._cooling_temp_offset_low = config.get("cooling_temp_offset_low")
        self._heating_temp_offset_high = config.get("heating_temp_offset_high")
        self._heating_temp_offset_low = config.get("heating_temp_offset_low")
        self._position_difference_threshold = config.get("position_difference_threshold", 5)
        self._min_open_percent = config.get('min_open_percent', 0.0)
        self._fully_open_entity_id = config.get('fully_open_entity_id')

    @property
    def temperature_entity_id(self):
        return self._temperature_entity_id

    @property
    def vent_entity_ids(self):
        return self._vent_entity_ids

    @property
    def cooling_temp_offset_high(self):
        return self._cooling_temp_offset_high

    @property
    def cooling_temp_offset_low(self):
        return self._cooling_temp_offset_low

    @property
    def heating_temp_offset_high(self):
        return self._heating_temp_offset_high

    @property
    def heating_temp_offset_low(self):
        return self._heating_temp_offset_low

    @property
    def position_difference_threshold(self):
        return self._position_difference_threshold

    @property
    def min_open_percent(self):
        return self._min_open_percent

    @property
    def fully_open_entity_id(self):
        return self._fully_open_entity_id
