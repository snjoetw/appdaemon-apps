from datetime import datetime
from statistics import mean

from alarm_notifier import AlarmNotifier
from climate.air_quality_monitor import AirQualityMonitor
from device_monitor import DeviceMonitor
from notifier import NotifierType

from lib.calendar_helper import CalendarEventFetcher
from lib.climate.air_quality_level import AirQualityLevel
from lib.constraints import get_constraint
from lib.context import Context
from lib.core.component import Component
from lib.core.config import Config
from lib.helper import concat_list, to_float, is_float
from lib.location_helper import LocationFetcher
from lib.presence_helper import PRESENCE_MODE_SOMEONE_IS_HOME, PRESENCE_MODE_EVERYONE_IS_HOME
from lib.time_wrapper import DateTimeWrapper
from lib.travel_time_helper import TravelTimeFetcher

TIME_TRIGGER_METHOD = 'time'
MOTION_TRIGGER_METHOD = 'motion'


def get_reminder_provider(app, config):
    provider = config['provider'];
    if provider == 'device_battery':
        return DeviceBatteryReminder(app, config)
    elif provider == 'travel_time':
        return TravelTimeReminder(app, config)
    elif provider == 'school_time':
        return SchoolDropOffTimeReminder(app, config)
    elif provider == 'drink_water':
        return DrinkWaterReminder(app, config)
    elif provider == 'bad_air_quality':
        return BadAirQualityReminder(app, config)
    elif provider == 'exceeds_threshold':
        return ExceedsThresholdMonitor(app, config)
    elif provider == 'climate_away_mode':
        return ClimateAwayModeReminder(app, config)
    elif provider == 'vent_issue':
        return VentIssueReminder(app, config)
    elif provider == 'left_on':
        return LeftOnReminder(app, config)
    elif provider == 'tesla_battery':
        return TeslaBatteryReminder(app, config)
    elif provider == 'abnormal_room_temperature':
        return AbnormalRoomTemperatureReminder(app, config)
    else:
        raise ValueError("Invalid reminder provider config: {}".format(config))


class ReminderProvider(Component):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)

        self._enabled = self.cfg.value('enabled', True)
        self._interval = self.cfg.int('interval', 30)
        self._trigger_method = self.cfg.value('trigger_method', TIME_TRIGGER_METHOD)

    @property
    def interval(self):
        return self._interval

    @property
    def enabled(self):
        return self._enabled

    @property
    def trigger_method(self):
        return self._trigger_method

    def can_provide(self, context: Context):
        mode = context.presence_mode
        return mode == PRESENCE_MODE_SOMEONE_IS_HOME or mode == PRESENCE_MODE_EVERYONE_IS_HOME

    def provide(self, context: Context):
        pass

    def log(self, msg, level="INFO"):
        provider_name = type(self).__name__
        return self.app.log('{} - {}'.format(provider_name, msg), level=level)


class SelfNotifiableReminderProvider(ReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)

    def notify(self, message_text, trigger_entity_id, settings=None):
        notify_config = Config(self.app, self.cfg.value('notify'))
        title = notify_config.value("title", None)
        notifier_types = [NotifierType(n) for n in notify_config.list('notifier', [])]
        if settings is None:
            settings = {
                NotifierType.IOS.value: notify_config.value(NotifierType.IOS.value, {})
            }

        notifier: AlarmNotifier = self.app.get_app('alarm_notifier')
        notifier.notify(notifier_types, title, message_text, trigger_entity_id, None, settings)


class DeviceBatteryReminder(ReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)

    def provide(self, context):
        device_monitor: DeviceMonitor = self.app.get_app('device_monitor')
        checker_result = device_monitor.get_checker_result('battery_level')

        if checker_result is None or not checker_result.has_error_device_result:
            return

        low_battery_device_names = []

        for result in checker_result.error_device_results:
            friendly_name = self.get_state(result.entity_id, attribute='friendly_name').replace('Battery', 'battery')
            low_battery_device_names.append(friendly_name)

        if not low_battery_device_names:
            return None

        if len(low_battery_device_names) == 1:
            message_text = '{} is running low'.format(low_battery_device_names[0])
        else:
            device_names = concat_list(low_battery_device_names)
            message_text = '{} are running low'.format(device_names)

        return ReminderMessage(message_text, '🔋 {}'.format(message_text))


class VentIssueReminder(ReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)

    def provide(self, context):
        device_monitor: DeviceMonitor = self.app.get_app('device_monitor')
        checker_result = device_monitor.get_checker_result('vent')

        if checker_result is None or not checker_result.has_error_device_result:
            return

        device_names = set()
        for result in checker_result.error_device_results:
            device_name = self.get_state(result.entity_id, attribute='friendly_name') \
                .replace('Temperature', '') \
                .replace('Battery', '') \
                .strip()

            device_names.add(device_name)

        if not device_names:
            return

        device_names = list(device_names)
        if len(device_names) == 1:
            return ReminderMessage('{} is having issue, please have a look.'.format(device_names[0]))
        elif len(device_names) == 2:
            return ReminderMessage('{} are having issue, please have a look.'.format(concat_list(device_names)))

        return ReminderMessage('{} and {} other vent are having issue, please have a look.'.format(
            device_names[0],
            len(device_names) - 1))


class SchoolDropOffTimeReminder(ReminderProvider):

    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)

        self.start_time = self.cfg.value('start_time', None)
        self.end_time = self.cfg.value('end_time', None)
        self.school_time = self.cfg.value('school_time', None)
        self.school_day_entity_id = self.cfg.value('school_day_entity_id', None)

    def can_provide(self, context):
        if not super().can_provide(context):
            return False

        if not self.app.now_is_between(self.start_time, self.end_time):
            self.debug('Skipping, not between {} and {}'.format(self.start_time,
                                                                self.end_time))
            return False

        if not self.get_state(self.school_day_entity_id) == 'on':
            self.debug('Skipping, not school day')
            return False

        return True

    def provide(self, context):
        time_diff = DateTimeWrapper(self.app, self.school_time).diff(datetime.now())
        time_diff_in_min = time_diff.total_seconds() / 60
        current_time = datetime.now().strftime('%H:%M')

        self.debug('time_diff_in_min={} vs threshold=15'.format(time_diff_in_min))

        if time_diff_in_min > 10:
            message_text = 'It\'s {}, time to get ready for school'.format(current_time)
        else:
            message_text = 'It\'s {}, you\'re running late for school'.format(current_time)

        return ReminderMessage(message_text, '⏱ {}'.format(message_text))


class TravelTimeReminder(SelfNotifiableReminderProvider):
    travel_time_fetcher: TravelTimeFetcher

    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)

        self.events_fetcher = CalendarEventFetcher(
            self,
            self.cfg.value('calendar_api_base_url', None),
            self.cfg.value('calendar_api_token', None),
        )

        self.home_location = self.cfg.value('map_home_location', None)
        self.travel_time_fetcher = TravelTimeFetcher(self, self.cfg.value('map_api_key', None))
        self.location_fetcher = LocationFetcher(self, self.cfg.value('map_api_key', None))

        self.calendar_entity_id = self.cfg.value('calendar_entity_id', None)
        self.buffer_time = self.cfg.int('buffer_time', None)

    def provide(self, context):
        event = self.events_fetcher.fetch_upcoming_event(self.calendar_entity_id, datetime.today())

        if not event:
            return

        time_diff = (event.start_time.replace(tzinfo=None) - datetime.now())
        time_diff_in_min = time_diff.total_seconds() / 60
        self.debug('Found upcoming event: {} - {} at {}, time_diff={}'.format(
            event.title,
            event.start_time,
            event.location,
            time_diff))

        if time_diff_in_min > 90 or time_diff_in_min < 5:
            return None

        travel_time = self.travel_time_fetcher.fetch_travel_time(
            self.home_location,
            event.location,
            'driving',
            departure_time=datetime.now()
        )

        self.debug('event_time={}, buffer_time={}, travel_time={}'.format(
            event.start_time,
            self.buffer_time,
            travel_time.duration_in_min,
        ))

        if time_diff_in_min > travel_time.duration_in_min + self.buffer_time:
            return None

        # if travel time is more than 2 hours, then probably the location is set incorrectly
        if travel_time.duration_in_min > 120:
            return None

        location = self.location_fetcher.fetch_location(travel_time.destination)

        self.debug(location)
        message_text = 'You\'re running late for {}, it will take {} min to {} in {}'.format(
            event.title,
            travel_time.duration_in_min,
            location.street,
            location.city)

        self.notify('⏳ {}'.format(message_text), None, {
            NotifierType.IOS.value: {
                'action_data': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'shows_points_of_interest': True,
                    'shows_traffic': True,
                    'shows_user_location': True,
                }
            }
        })

        return ReminderMessage(message_text, send_aggregated_notification=False)


class TeslaBatteryReminder(ReminderProvider):
    travel_time_fetcher: TravelTimeFetcher

    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)

        self.range_entity_id = self.cfg.value('range_entity_id', None)
        self.reserved_range = self.cfg.value('reserved_range', 100)
        self.events_fetcher = CalendarEventFetcher(
            self,
            self.cfg.value('calendar_api_base_url', None),
            self.cfg.value('calendar_api_token', None),
        )
        self.home_location = self.cfg.value('map_home_location', None)
        self.travel_time_fetcher = TravelTimeFetcher(self, self.cfg.value('map_api_key', None))

    def provide(self, context):
        current_range = self.get_state(self.range_entity_id) - self.reserved_range
        if current_range <= 0:
            return ReminderMessage('Model X is running low in battery.')

        event = self.events_fetcher.fetch_upcoming_event(self.calendar_entity_id, datetime.today())

        if not event or not event.location:
            return

        travel_time = self.travel_time_fetcher.fetch_travel_time(
            self.home_location,
            event.location,
            'driving',
            departure_time=datetime.now()
        )

        if not travel_time:
            return

        round_trip_distance = travel_time.distance * 2
        if round_trip_distance < current_range:
            return

        return ReminderMessage('Model X does not have enough range to get to {}'.format(event.title))


class DrinkWaterReminder(ReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)
        self.start_time = self.cfg.value('start_time', None)
        self.end_time = self.cfg.value('end_time', None)

    def can_provide(self, context):
        if not super().can_provide(context):
            return False

        if not self.app.now_is_between(self.start_time, self.end_time):
            return False

        return True

    def provide(self, context):
        return ReminderMessage('Remember to drink water')


class ExceedsThresholdMonitor(ReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)
        self.settings = self.cfg.list('settings')
        self.thresholds = self.cfg.list('thresholds')

    def provide(self, context):
        for setting in self.settings:
            entity_id = setting.get('entity_id')
            area_name = setting.get('name')
            current_level = to_float(self.app.get_state(entity_id))

            if current_level is None:
                self.warn('Invalid current_level (None) for entity_id={}'.format(entity_id))
                continue

            for threshold_config in self.thresholds:
                if current_level >= threshold_config['threshold']:
                    return ReminderMessage(threshold_config['message'].format(area_name))


class BadAirQualityReminder(ReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)
        self.bad_air_quality_mode_entity_id = self.cfg.value('bad_air_quality_mode_entity_id', None)

    def can_provide(self, context):
        if not super().can_provide(context):
            return False

        bad_air_quality_mode = self.app.get_state(self.bad_air_quality_mode_entity_id)
        if bad_air_quality_mode == 'off':
            return False

        return True

    def provide(self, context):
        app: AirQualityMonitor = self.app.get_app('air_quality_monitor')
        bad_monitors = []
        very_bad_monitors = []
        for monitor, level in app.get_bad_air_quality_monitors().items():
            if level is AirQualityLevel.BAD:
                bad_monitors.append(monitor.name)
            elif level is AirQualityLevel.VERY_BAD:
                very_bad_monitors.append(monitor.name)

        if not bad_monitors and not very_bad_monitors:
            return

        if not bad_monitors:
            name = concat_list(very_bad_monitors)
            return ReminderMessage('Attention, air quality is very bad in {}'.format(name))
        if not very_bad_monitors:
            name = concat_list(bad_monitors)
            return ReminderMessage('Attention, air quality is bad in {}'.format(name))

        return ReminderMessage('Attention, air quality is bad in {} and very bad in {}'.format(
            concat_list(bad_monitors),
            concat_list(very_bad_monitors)
        ))


class ClimateAwayModeReminder(ReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)
        self.climate_entity_id = self.cfg.value('climate_entity_id', None)

    def provide(self, context):
        if self.get_state(self.climate_entity_id) == 'off' and self.is_sleeping_time:
            return ReminderMessage('Ecobee is still turned off')

        preset_mode = self.get_state(self.climate_entity_id, attribute='preset_mode')
        if preset_mode == 'Away':
            return ReminderMessage('Ecobee is still in away mode')


class AbnormalRoomTemperatureReminder(ReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)
        self.room_configs = self.cfg.list('rooms')
        self.temperature_entity_ids = [c['temperature_entity_id'] for c in self.room_configs]
        self.threshold = self.cfg.float('threshold', 0.1)

    def provide(self, context):
        temperatures = [t for t in [self.float_state(e) for e in self.temperature_entity_ids] if is_float(t)]
        average_temperature = mean(temperatures)
        above_average_rooms = []
        for c in self.room_configs:
            temperature = self.float_state(c['temperature_entity_id'])
            if not temperature:
                continue
            diff = (temperature - average_temperature) / average_temperature
            if diff > self.threshold:
                self.log(
                    '{} temperature is above average, average_temperature={}, threshold={}, diff={}'.format(
                        c['name'],
                        average_temperature,
                        self.threshold,
                        diff))
                above_average_rooms.append(c['name'])

        if not above_average_rooms:
            self.debug('No above average rooms found, average_temperature={}, threshold={}'.format(average_temperature,
                                                                                                   self.threshold))
            return

        return ReminderMessage('Temperature is above average in ' + concat_list(
            above_average_rooms) + '. Please consider open the window or close the blind.')


class LeftOnReminder(SelfNotifiableReminderProvider):
    def __init__(self, app, reminder_config):
        super().__init__(app, reminder_config)
        self.settings = self.cfg.list('settings')
        self.thresholds = self.cfg.list('thresholds')
        self.message = self.cfg.value('message')
        self.message_plural = self.cfg.value('message_plural')

    def provide(self, context):
        self.debug('Checking, thresholds={}'.format(self.thresholds))
        left_on_entity_ids = []
        first_exceeded_threshold_entity_id = None
        now = datetime.now()

        for threshold_config in self.thresholds:
            config = Config(self.app, threshold_config)
            threshold_in_seconds = config.int('threshold')
            entity_ids = config.list('entity_id')

            if self.should_skip_threshold_check(context, now, threshold_in_seconds):
                self.debug('Skipping, last_trigger_time={}, threshold_in_seconds={}'.format(context.last_trigger_time,
                                                                                            threshold_in_seconds))
                continue

            additional_constraints = [get_constraint(self.app, c) for c in config.list('constraints', [])]
            if not self.check_additional_constraints(additional_constraints):
                continue

            left_on_entity_ids.extend(self.exceeded_threshold_entity_ids(entity_ids, threshold_in_seconds))

            if left_on_entity_ids and first_exceeded_threshold_entity_id is None:
                first_exceeded_threshold_entity_id = left_on_entity_ids[0]

        self.debug('Found {} entities left on for too long'.format(len(left_on_entity_ids)))

        if not left_on_entity_ids:
            return

        left_on_entity_names = [self.get_state(entity_id, attribute='friendly_name').capitalize()
                                for entity_id in left_on_entity_ids]
        message = self.figure_message(left_on_entity_names)
        self.notify("⚠️ " + message, first_exceeded_threshold_entity_id)

        return ReminderMessage(message, send_aggregated_notification=False)

    def should_skip_threshold_check(self, context, now, threshold_in_seconds):
        if context.last_trigger_time is None:
            return False

        difference = (now - context.last_trigger_time).total_seconds()
        return difference < threshold_in_seconds

    def exceeded_threshold_entity_ids(self, entity_ids, threshold_in_seconds):
        left_on_entity_id = []
        for entity_id in entity_ids:
            if not self.is_state_on(entity_id):
                continue

            state_last_changed_duration = self.state_last_changed_duration(entity_id)
            exceeded_threshold = state_last_changed_duration > threshold_in_seconds

            self.debug('Checking {}, threshold={}, left_on={}, exceeded_threshold={}'.format(
                entity_id, threshold_in_seconds, state_last_changed_duration, exceeded_threshold))

            if exceeded_threshold:
                left_on_entity_id.append(entity_id)

        return left_on_entity_id

    def figure_message(self, left_on_entity_names):
        if len(left_on_entity_names) == 1:
            return self.message.format(left_on_entity_names[0])
        return self.message_plural.format(concat_list(left_on_entity_names))

    def check_additional_constraints(self, additional_constraints):
        if not additional_constraints:
            return True

        for constraint in additional_constraints:
            if not constraint.check(None):
                self.debug('Additional constraint does not match {}'.format(constraint))
                return False

        self.debug('All additional constraints passed')
        return True


class ReminderMessage:
    def __init__(self, announcement_text, notifier_text=None, send_aggregated_notification=True):
        self._announcement_text = announcement_text
        self._notifier_text = announcement_text if notifier_text is None else notifier_text
        self._send_aggregated_notification = send_aggregated_notification

    @property
    def announcement_text(self):
        return self._announcement_text

    @property
    def notifier_text(self):
        return self._notifier_text

    @property
    def send_aggregated_notification(self):
        return self._send_aggregated_notification
