from enum import IntEnum

from base_automation import BaseAutomation
from lib.climate.air_quality_level import AirQualityLevel
from lib.core.monitored_callback import monitored_callback


# PM10
#   0-50    Good
#   51-75   Fair
#   76-100  Poor
#   101-350 Very Poor

# PM2.5
#   0-35    Good
#   36-53   Fair
#   54-70   Poor
#   71-150  Very Poor

class AirQualityLevel(IntEnum):
    GOOD = 1
    FAIR = 2
    POOR = 3
    VERY_POOR = 4

    def name(self):
        """The name of the Enum member."""
        return self._name_


class RoomConfig:
    def __init__(self, config):
        self._air_quality_level_entity_id = config['air_quality_level_entity_id']
        self._sensor_configs = [SensorConfig(c) for c in config['sensors']]
        self._name = config['name']

    @property
    def air_quality_level_entity_id(self):
        return self._air_quality_level_entity_id

    @property
    def name(self):
        return self._name

    @property
    def sensor_configs(self):
        return self._sensor_configs


class SensorConfig:
    def __init__(self, config):
        self._sensor_entity_id = config['sensor_entity_id']
        self._name = config['name']
        self._threshold_configs = [ThresholdConfig(c) for c in config['thresholds']]

    @property
    def sensor_entity_id(self):
        return self._sensor_entity_id

    @property
    def name(self):
        return self._name

    @property
    def threshold_configs(self):
        return self._threshold_configs


class ThresholdConfig:
    def __init__(self, config):
        self._level = AirQualityLevel[config['level']]
        self._value = config['value']

    @property
    def level(self):
        return self._level

    @property
    def value(self):
        return self._value


class AirQualityMonitor(BaseAutomation):
    def initialize(self):
        self._room_configs = [RoomConfig(r) for r in self.cfg.value('rooms')]
        self._overall_air_quality_level_entity_id = self.cfg.value('overall_air_quality_level_entity_id')

        for room_config in self._room_configs:
            for sensor_config in room_config.sensor_configs:
                self.listen_state(self._sensor_state_change_handler, sensor_config.sensor_entity_id, immediate=True)

    @monitored_callback
    def _sensor_state_change_handler(self, entity, attribute, old, new, kwargs):
        worst_sensor_level = None

        for room_config in self._room_configs:
            (sensor_name, sensor_level) = self._figure_room_level(room_config)

            entity = self.get_state(room_config.air_quality_level_entity_id, attribute="all")
            attributes = {} if entity is None else entity["attributes"]
            attributes['last_triggered_by'] = sensor_name
            self._set_air_quality_level(room_config.air_quality_level_entity_id, sensor_level, attributes=attributes)

            if worst_sensor_level is None or worst_sensor_level < sensor_level:
                worst_sensor_level = sensor_level

        self._set_air_quality_level(self._overall_air_quality_level_entity_id, worst_sensor_level)

    def _set_air_quality_level(self, entity_id, sensor_level, attributes={}):
        level_str = str(sensor_level).replace('AirQualityLevel.', '')
        self.set_state(entity_id, state=level_str, attributes=attributes)

    def _figure_room_level(self, room_config):
        self.debug('Checking {}'.format(room_config.name))

        sensor_by_level = {}
        for sensor_config in room_config.sensor_configs:
            self.debug('Checking {}'.format(sensor_config.name))

            level = self._figure_sensor_level(sensor_config)

            self.debug('Checked sensor, name={}, level={}'.format(sensor_config.name, level))

            # only set sensor_by_level if it's not seen previously
            if level not in sensor_by_level:
                sensor_by_level[level] = sensor_config.name

        for air_quality_level in reversed(list(map(int, AirQualityLevel))):
            if air_quality_level in sensor_by_level:
                return sensor_by_level[air_quality_level], AirQualityLevel(air_quality_level)

        return None, AirQualityLevel.GOOD

    def _figure_sensor_level(self, sensor_config):
        sensor_value = self.int_state(sensor_config.sensor_entity_id)
        if sensor_value is None:
            self.warn("No sensor value, entity_id={}".format(sensor_config.sensor_entity_id))
            return None

        for threshold_config in sensor_config.threshold_configs:
            if sensor_value >= threshold_config.value:
                return threshold_config.level

        return AirQualityLevel.GOOD
