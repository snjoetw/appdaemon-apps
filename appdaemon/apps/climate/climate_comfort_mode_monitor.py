from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback


class ClimateComfortModeMonitor(BaseAutomation):
    def initialize(self):
        self.climate_comfort_level_entity_id = self.cfg.value('climate_comfort_level_entity_id')
        self.comfort_threshold = self.cfg.value('comfort_temp_threshold', 0.7)
        self.temperature_entity_id = self.cfg.value('temperature_entity_id')
        self.target_temperature_high_entity_id = self.cfg.value('target_temp_high')
        self.target_temperature_low_entity_id = self.cfg.value('target_temp_low')

        self.listen_state(self.state_change_handler, self.temperature_entity_id, immediate=True)

    @monitored_callback
    def state_change_handler(self, entity, attribute, old, new, kwargs):
        if new == 'unavailable':
            return

        current_temp = self.float_state(self.temperature_entity_id)
        target_temp_high = self.float_state(self.target_temperature_high_entity_id)
        target_temp_low = self.float_state(self.target_temperature_low_entity_id)

        if not current_temp or not target_temp_high or not target_temp_low:
            self.warn('Missing required values, {} => {}, {} => {}, {} => {}'.format(self.temperature_entity_id,
                                                                                     current_temp,
                                                                                     self.target_temperature_high_entity_id,
                                                                                     target_temp_high,
                                                                                     self.target_temperature_low_entity_id,
                                                                                     target_temp_low))
            return

        comfort_range = self.get_comfort_range(target_temp_high, target_temp_low)
        warm_range = range_open_closed(comfort_range.end, target_temp_high)
        cool_range = range_closed_open(target_temp_low, comfort_range.start)

        if comfort_range.contains(current_temp):
            self.set_climate_comfort_level_value('Comfort')
        elif warm_range.contains(current_temp):
            self.set_climate_comfort_level_value('Warm')
        elif cool_range.contains(current_temp):
            self.set_climate_comfort_level_value('Cool')
        elif current_temp > warm_range.end:
            self.set_climate_comfort_level_value('Hot')
        elif current_temp < cool_range.end:
            self.set_climate_comfort_level_value('Cold')

    def get_comfort_range(self, target_temp_high, target_temp_low):
        target_mid_temp = self.get_target_mid_temperature(target_temp_high, target_temp_low)
        return range_closed(target_mid_temp - self.comfort_threshold, target_mid_temp + self.comfort_threshold)

    def get_target_mid_temperature(self, target_temp_high, target_temp_low):
        return (target_temp_high - target_temp_low) / 2 + target_temp_low

    def set_climate_comfort_level_value(self, new_mode_value):
        self.select_option(self.climate_comfort_level_entity_id, new_mode_value)


def range_open(start, end):
    return Range(start, end, False, False)


def range_closed(start, end):
    return Range(start, end, True, True)


def range_open_closed(start, end):
    return Range(start, end, False, True)


def range_closed_open(start, end):
    return Range(start, end, True, False)


class Range:
    def __init__(self, start, end, include_start=True, include_end=True):
        self._start = start
        self._end = end
        self._include_start = include_start
        self._include_end = include_end

    @property
    def start(self):
        return self._start

    @property
    def end(self):
        return self._end

    def contains(self, value):
        # open
        # {x | a < x < b}
        if self._include_start is False and self._include_end is False:
            return self._start < value < self._end
        # closed
        # {x | a <= x <= b}
        elif self._include_start is True and self._include_end is True:
            return self._start <= value <= self._end
        # open, closed
        # {x | a < x <= b}
        elif self._include_start is False and self._include_end is True:
            return self._start < value <= self._end
        # closed, open
        # {x | a <= x < b}
        elif self._include_start is True and self._include_end is False:
            return self._start <= value < self._end
