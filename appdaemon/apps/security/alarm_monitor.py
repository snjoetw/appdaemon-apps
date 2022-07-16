from appdaemon.utils import run_async_sync_func
from typing import List

from alarm_notifier import AlarmNotifier
from async_base_automation import AsyncBaseAutomation
from lib.helper import STATE_ON, STATE_ARMED_HOME, STATE_ARMED_AWAY
from notifier import NotifierType

DEFAULT_NOTIFY_MESSAGE = 'WARNING: **{}** is opened while alarm is armed'
MOTION_NOTIFY_MESSAGE = 'WARNING: **{}** detected while alarm is armed'


class AlarmMonitor(AsyncBaseAutomation):
    _door_entity_ids: List[str]
    _window_entity_ids: List[str]
    _motion_entity_ids: List[str]

    async def initialize(self):
        self._door_entity_ids = self.cfg.list('door_entity_id')
        self._window_entity_ids = self.cfg.list('window_entity_id')
        self._motion_entity_ids = self.cfg.list('motion_entity_id')
        self._alarm_entity_id = self.cfg.value('alarm_entity_id')
        self._alarm_motion_bypass_entity_id = self.cfg.value('alarm_motion_bypass_entity_id')

        for entity_id in self._door_entity_ids + self._window_entity_ids + self._motion_entity_ids:
            self.listen_state(self._state_change_handler, entity_id)

    async def _state_change_handler(self, entity_id, attribute, old, new, kwargs):
        if new != STATE_ON:
            return

        alarm_state = await self.get_state(self._alarm_entity_id)
        if alarm_state != STATE_ARMED_AWAY and alarm_state != STATE_ARMED_HOME:
            return

        if not await self.should_trigger_alarm(entity_id):
            return

        notify_message = await self.figure_notify_message(entity_id)
        # TODO: replace this with async app API call
        await run_async_sync_func(self, self.notify, notify_message, entity_id)

    def notify(self, notify_message, entity_id):
        notifier: AlarmNotifier = self.get_app('alarm_notifier')
        notifier.notify([NotifierType.IOS], None, '‼️ ' + notify_message, entity_id, None, {
            NotifierType.IOS.value: {
                'notification_template_name': 'alarm_armed_away_motion_triggered',
                'critical': True,
            }
        })

    async def should_trigger_alarm(self, entity_id):
        if not self.is_motion_entity_id(entity_id):
            return True

        alarm_state = await self.get_state(self._alarm_entity_id)
        if alarm_state != STATE_ARMED_AWAY:
            return False

        is_alarm_motion_bypass = await self.get_state(self._alarm_motion_bypass_entity_id)
        return is_alarm_motion_bypass != 'on'

    async def figure_notify_message(self, entity_id):
        friendly_name = await self.get_state(entity_id, attribute='friendly_name')
        friendly_name = friendly_name.capitalize()
        if self.is_motion_entity_id(entity_id):
            return MOTION_NOTIFY_MESSAGE.format(friendly_name)
        else:
            return DEFAULT_NOTIFY_MESSAGE.format(friendly_name)

    def is_motion_entity_id(self, entity_id):
        return entity_id in self._motion_entity_ids
