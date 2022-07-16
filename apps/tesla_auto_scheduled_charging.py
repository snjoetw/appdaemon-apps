from datetime import datetime, timedelta

import requests

from base_automation import BaseAutomation
from lib.calendar_helper import CalendarEventFetcher
from lib.core.monitored_callback import monitored_callback
from lib.helper import to_float
from lib.travel_time_helper import TravelTimeFetcher

STATE_WAITING = 'WAITING'
STATE_CHARGING = 'CHARGING'
STATE_CHARGED = 'CHARGED'
STATE_SKIPPED = 'SKIPPED'

# how often the app should check if auto charge is needed in seconds
CHECK_FREQUENCY = 600
# time threshold between future event and now in minutes
AUTO_CHARGE_TIME_THRESHOLD = 45
# % to auto charge
AUTO_CHARGE_PERCENT = 10


class TeslaAutoScheduledCharging(BaseAutomation):

    def initialize(self):
        self.events_fetcher = CalendarEventFetcher(self,
                                                   self.cfg.value('calendar_api_base_url'),
                                                   self.cfg.value('calendar_api_token'))
        self.travel_time_fetcher = TravelTimeFetcher(self, self.cfg.value('map_api_key'))
        self.buffer_time = self.cfg.int('buffer_time', 10)
        self.home_location = self.cfg.value('map_home_location')

        self.enabler_entity_id = self.cfg.value('enabler_entity_id')
        self.auto_charge_state_entity_id = self.cfg.value('auto_charge_state_entity_id')
        self.calendar_entity_id = self.cfg.value('calendar_entity_id')
        self.school_day_entity_id = self.cfg.value('school_day_entity_id')
        self.work_day_entity_id = self.cfg.value('work_day_entity_id')
        self.tesla_state_entity_id = self.cfg.value('tesla_state_entity_id')
        self.tesla_plugged_in_entity_id = self.cfg.value('tesla_plugged_in_entity_id')
        self.tesla_location_entity_id = self.cfg.value('tesla_location_entity_id')
        self.tesla_charge_limit_entity_id = self.cfg.value('tesla_charge_limit_entity_id')
        self.tesla_resume_logging_url = self.cfg.value('tesla_resume_logging_url')
        self.school_time = self.cfg.value('school_time')

        self.original_charge_limit = None
        self.last_charged_time = None
        self.last_check_time = datetime.now()

        self.run_every(self.run_every_handler, datetime.now(), CHECK_FREQUENCY)

    @monitored_callback
    def run_every_handler(self, time=None, **kwargs):
        if self.last_check_time.date() != datetime.today().date():
            self.set_auto_charge_state(STATE_WAITING)

        current_state = self.get_state(self.auto_charge_state_entity_id)

        if current_state == STATE_WAITING:
            self.handle_idle_state()
        elif current_state == STATE_CHARGING:
            self.handle_charging_state()
        elif current_state == STATE_CHARGED:
            self.handle_charged_state()
        elif current_state == STATE_SKIPPED:
            self.handle_skipped_state()

        self.last_check_time = datetime.now()

    def handle_idle_state(self):
        if not self.should_auto_charge():
            self.debug('Skipping ... should NOT auto charge')
            return

        # start teslamate logging
        requests.put(self.tesla_resume_logging_url)

        self.sleep(10)

        self.set_auto_charge_state(STATE_CHARGING)
        self.original_charge_limit = self.float_state(self.tesla_charge_limit_entity_id)
        auto_charge_limit = self.original_charge_limit + AUTO_CHARGE_PERCENT

        tesla_proxy = self.get_app('tesla_proxy')
        tesla_proxy.set_charge_limit(auto_charge_limit)

        self.debug('About to charge, original_charge_limit={}, auto_charge_limit={}'.format(
            self.original_charge_limit,
            auto_charge_limit,
        ))

    def handle_charging_state(self):
        tesla_state = self.get_state(self.tesla_state_entity_id)
        if tesla_state == 'charging':
            self.debug('Skipping ... still charging')
            return

        current_charge_limit = self.float_state(self.tesla_charge_limit_entity_id)
        if current_charge_limit == self.original_charge_limit:
            self.debug('Auto charge limit not being set, fixing ...')
            self.handle_idle_state()
            return

        plugged_in = self.get_state(self.tesla_plugged_in_entity_id)
        if plugged_in == 'true':
            self.debug(
                'Skipping ... not charging ({}) but still plugged in'.format(
                    tesla_state))
            return

        self.set_auto_charge_state(STATE_CHARGED)
        self.last_charged_time = datetime.now()

        tesla_proxy = self.get_app('tesla_proxy')
        tesla_proxy.set_charge_limit(self.original_charge_limit)

        self.debug('Done charging, charge_limit={}'.format(
            self.original_charge_limit
        ))

    def handle_charged_state(self):
        if self.last_charged_time is not None \
                and self.last_charged_time.date() == datetime.today().date():
            self.debug('Skipping ... already auto charged')
            return

        self.set_auto_charge_state(STATE_WAITING)
        self.original_charge_limit = None
        self.last_charged_time = None

        self.debug('Reset state to waiting from charged')

    def handle_skipped_state(self):
        if self.last_check_time.date() == datetime.today().date():
            self.debug('Skipping for today')
            return

        self.set_auto_charge_state(STATE_WAITING)
        self.original_charge_limit = None
        self.last_charged_time = None

        self.debug('Reset state to waiting from skipped')

    def should_auto_charge(self):
        is_enabled = self.get_state(self.enabler_entity_id)
        if is_enabled != 'on':
            self.debug('Skipping ... auto charging not enabled')
            return False

        plugged_in = self.get_state(self.tesla_plugged_in_entity_id)
        if plugged_in != 'true':
            self.debug('Skipping ... not plugged in')
            return False

        tesla_state = self.get_state(self.tesla_state_entity_id)
        if tesla_state == 'charging':
            self.debug('Skipping ... already charging')
            return False

        charge_limit = self.float_state(self.tesla_charge_limit_entity_id)
        if charge_limit >= 85:
            self.debug('Skipping ... charge limit is {}'.format(charge_limit))
            return False

        location = self.get_state(self.tesla_location_entity_id)
        # if location != 'home':
        #         #     return False

        event_time = self.figure_next_event_time()
        if not event_time:
            self.debug('Skipping ... no event found')
            return False

        time_diff = event_time - datetime.now()
        time_diff_in_min = time_diff.total_seconds() / 60

        self.debug('Upcoming event_time={}, time_diff_in_min={}'.format(
            event_time, time_diff_in_min))

        return time_diff_in_min < AUTO_CHARGE_TIME_THRESHOLD

    def figure_next_event_time(self):
        school_time = self.figure_school_time()
        event = self.fetch_next_event()

        if not school_time and not event:
            return None

        if not event:
            return school_time

        travel_time = self.travel_time_fetcher.fetch_travel_time(
            self.home_location,
            event.location,
            'driving',
            departure_time=datetime.now())

        travel_time_in_min = travel_time.duration_in_min + self.buffer_time
        event_time = event.start_time.replace(tzinfo=None) - timedelta(minutes=travel_time_in_min)

        self.debug('travel_time_in_min={}, event_time={}'.format(travel_time_in_min, event_time))

        if not school_time:
            return event_time

        if school_time > event_time:
            return event_time

        return school_time

    def fetch_next_event(self):
        event = self.events_fetcher.fetch_upcoming_event(
            self.calendar_entity_id,
            datetime.today())

        if not event or not event.location:
            return None

        return event

    def figure_school_time(self):
        is_school_day = self.get_state(self.school_day_entity_id)
        is_work_day = self.get_state(self.work_day_entity_id)
        if is_school_day == 'on' or is_work_day == 'on':
            return datetime.combine(datetime.today(), self.parse_time(self.school_time))
        return None

    def set_auto_charge_state(self, state):
        self.select_option(self.auto_charge_state_entity_id, state)
