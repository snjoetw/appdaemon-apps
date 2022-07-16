from datetime import datetime, timedelta

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback
from lib.helper import to_int
from notifier import Notifier, Message, NotifierType

STATE_TRACKING = "Tracking"
STATE_COMPLETED = "Completed"
PILLS_TAKEN_ACTION_PREFIX = "PILLS_TAKEN_"
ACTION_EMOJIS = ['👍', '🤟', '🎉', '✅']


def create_pills_left_actions(pills_left, max_pills):
    actions = []

    for i in range(pills_left):
        pills_taken = str(i + 1)
        actions.append({
            'action': PILLS_TAKEN_ACTION_PREFIX + pills_taken,
            'title': ACTION_EMOJIS[max_pills - pills_left + i] + ' ' + pills_taken,
        })

    return actions


class MedicineIntakeTracker(BaseAutomation):

    def initialize(self):
        self._state_entity_id = self.cfg.value('state_entity_id')
        self._count_entity_id = self.cfg.value('count_entity_id')
        self._max_pill_count = self.cfg.int('max_pill_count')
        self._pill_box_entity_id = self.cfg.value('pill_box_entity_id')

        self.run_daily(self._run_daily_handler, "00:00:00")
        self.listen_state(self._pill_box_state_change_handler, self._pill_box_entity_id, new="on")
        self.listen_event(self._pills_taken_event_change_handler, 'mobile_app_notification_action')
        self.run_every(self._run_every_handler, datetime.now() + timedelta(seconds=2), 7200)

    @monitored_callback
    def _run_daily_handler(self, time=None, **kwargs):
        self._set_state(STATE_TRACKING)
        self._set_count(0)

    @monitored_callback
    def _run_every_handler(self, time=None, **kwargs):
        if not self._should_notify():
            return

        self._notify('💊 Remember to take medicine! How many pills did you take?')

    @monitored_callback
    def _pill_box_state_change_handler(self, entity, attribute, old, new, kwargs):
        if not self._should_notify():
            return

        self._notify('💊 How many pills did you take?')

    @monitored_callback
    def _pills_taken_event_change_handler(self, event_name, data, kwargs):
        action = data.get('action')
        if not action.startswith(PILLS_TAKEN_ACTION_PREFIX):
            return

        pills_taken = to_int(action[len(PILLS_TAKEN_ACTION_PREFIX):])
        total_pills_taken = pills_taken + self.int_state(self._count_entity_id)

        if total_pills_taken >= self._max_pill_count:
            total_pills_taken = self._max_pill_count
            self._set_state(STATE_COMPLETED)

        self._set_count(total_pills_taken)

    def _should_notify(self):
        if self.get_state(self._state_entity_id) == STATE_COMPLETED:
            self.debug('Completed medicine intake for today, skipping')
            return False

        if self.is_sleeping_time:
            self.debug('In sleeping time, skipping')
            return False

        return True

    def _set_state(self, state):
        self.set_state(self._state_entity_id, state=state)

    def _set_count(self, count):
        self.call_service('input_number/set_value', entity_id=self._count_entity_id, value=count)

    def _notify(self, message):
        pills_left = self._max_pill_count - self.int_state(self._count_entity_id)
        settings = {
            NotifierType.IOS.value: {
                'actions': create_pills_left_actions(pills_left, self._max_pill_count)
            }
        }

        notifier: Notifier = self.get_app('notifier')
        notifier.notify(Message([NotifierType.IOS], ['joe'], None, message, settings=settings))
