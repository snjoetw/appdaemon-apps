from datetime import datetime, time

from base_automation import BaseAutomation
from lib.calendar_helper import CalendarEventFetcher, is_no_school_event
from lib.core.monitored_callback import monitored_callback


class SchoolDayMonitor(BaseAutomation):

    def initialize(self):
        self.events_fetcher = CalendarEventFetcher(
            self,
            self.cfg.value('calendar_api_base_url'),
            self.cfg.value('calendar_api_token'),
        )

        self.calendar_entity_id = self.cfg.value('calendar_entity_id')
        self.workday_entity_id = self.cfg.value('workday_entity_id')
        self.school_day_entity_id = self.cfg.value('school_day_entity_id')

        runtime = time(0, 15, 0)
        self.run_daily(self.run_daily_hanlder, runtime)

        # force a run first
        self.run_daily_hanlder()

    @monitored_callback
    def run_daily_hanlder(self, time=None, **kwargs):
        if not self.get_state(self.workday_entity_id) == 'on':
            self.debug('Not workday')
            self.set_school_day(False)
            return

        is_school_day = self.is_school_day()
        self.set_school_day(is_school_day)

    def is_school_day(self):
        events = self.events_fetcher.fetch_all_day_events(
            self.calendar_entity_id,
            datetime.today())

        self.debug('Found {} events, {}'.format(len(events), events))
        no_school_events = [e for e in events if is_no_school_event(e)]
        self.debug('Found {} no school events'.format(len(no_school_events)))

        return not no_school_events

    def set_school_day(self, is_school_day):
        current = self.get_state(self.school_day_entity_id) == 'on'
        if current == is_school_day:
            return

        self.log('Setting is_school_day to {}'.format(is_school_day))

        if is_school_day:
            self.turn_on(self.school_day_entity_id)
        else:
            self.turn_off(self.school_day_entity_id)
