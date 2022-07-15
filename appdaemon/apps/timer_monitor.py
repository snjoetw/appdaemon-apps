from datetime import datetime, timedelta
from typing import List, Dict, Any

from announcer import Announcer
from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback

ONE_MINUTE = timedelta(minutes=1)
FIVE_MINUTES = timedelta(minutes=5)
TEN_MINUTES = timedelta(minutes=10)
THIRTY_MINUTES = timedelta(minutes=30)

TIMER_REMINDER_TEXT = 'You have {} minutes remaining on your {}'
HALF_WAY_REMINDER_TEXT = 'You\'re half way into {} on your {}'
TIMER_IS_UP_REMINDER_TEXT = 'Your {} is up'


class TimerReminder:
    def __init__(self, fire_time, text):
        self._fire_time = fire_time
        self._text = text

    @property
    def fire_time(self):
        return self._fire_time

    @property
    def text(self):
        return self._text


class TimerMonitor(BaseAutomation):
    _handles: Dict[str, List[Any]]

    def initialize(self):
        self._handles = {}
        for timer_entity_id in self.cfg.list('timer_entity_id'):
            self.listen_state(self.timer_state_change_handler, timer_entity_id, immediate=True)

    @monitored_callback
    def timer_state_change_handler(self, entity_id, attribute, old, new, kwargs):
        self.debug('Timer ({}) changed ({}), {} => {}'.format(entity_id, attribute, old, new))

        entity = self.get_state(entity_id, attribute='all')

        self.cancel_timer_handles(entity_id)

        if entity['state'] == 'unavailable':
            return

        attributes = entity.get('attributes', {})
        timers = attributes.get('timers', [])
        if not timers:
            return

        timer = timers[0]
        duration = self.to_timedelta(timer.get('duration'))
        fire_time = datetime.fromtimestamp(timer.get('fire_time'))
        friendly_name = attributes.get('friendly_name').lower()
        self.log('New timer, duration={}, fire_time={}'.format(duration, fire_time))
        reminders = self.figure_reminders(friendly_name, duration, fire_time)

        for reminder in reminders:
            self.log('Adding reminder, fire_time={}, text={}'.format(reminder.fire_time, reminder.text))
            handle = self.run_at(self.reminder_runner, reminder.fire_time, reminder=reminder)
            self._handles[entity_id].append(handle)

    @monitored_callback
    def reminder_runner(self, kwargs):
        reminder = kwargs['reminder']
        self.log('Running reminder, fire_time={}, text={}'.format(reminder.fire_time, reminder.text))
        announcer: Announcer = self.get_app('announcer')
        announcer.announce(reminder.text, use_cache=True)

    def cancel_timer_handles(self, timer_entity_id):
        handles = self._handles.get(timer_entity_id, [])
        for handle in handles:
            self.debug('Cancelled handle={}'.format(handle))
            self.cancel_timer(handle)

        self._handles[timer_entity_id] = []

    def figure_reminders(self, timer_name: str, duration: timedelta, fire_time: datetime) -> List[TimerReminder]:
        reminders = []

        if duration < ONE_MINUTE:
            return reminders

        reminders.append(TimerReminder(fire_time, TIMER_IS_UP_REMINDER_TEXT.format(timer_name)))
        if duration <= FIVE_MINUTES:
            return reminders

        reminders.append(TimerReminder(fire_time - FIVE_MINUTES, TIMER_REMINDER_TEXT.format(5, timer_name)))
        if duration <= TEN_MINUTES:
            return reminders

        reminders.append(TimerReminder(fire_time - TEN_MINUTES, TIMER_REMINDER_TEXT.format(10, timer_name)))
        if duration < THIRTY_MINUTES:
            return reminders

        halfway = timedelta(seconds=duration.total_seconds() / 2)
        duration_text = self.figure_duration_text(duration)
        reminders.append(TimerReminder(fire_time - halfway, HALF_WAY_REMINDER_TEXT.format(duration_text, timer_name)))
        return reminders

    @staticmethod
    def figure_duration_text(duration: timedelta):
        text = ''

        if duration.days == 1:
            text = text + '1 day '
        elif duration.days > 1:
            text = text + '{} days '.format(duration.days)

        hours = duration.seconds // 3600
        if hours == 1:
            text = text + '1 hour '
        elif hours > 1:
            text = text + '{} hours '.format(hours)

        minutes = (duration.seconds // 60) % 60
        if minutes > 0:
            text = text + '{} minutes'.format(minutes)

        return text.strip()

    @staticmethod
    def to_timedelta(s: str) -> timedelta:
        t = datetime.strptime(s, "%H:%M:%S")
        return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
