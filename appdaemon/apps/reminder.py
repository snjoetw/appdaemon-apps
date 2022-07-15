import traceback
from datetime import datetime

from announcer import Announcer
from configurable_automation import ConfigurableAutomation
from lib.actions import Action
from lib.briefing_helper import MEDIUM_PAUSE
from lib.context import Context
from lib.helper import figure_parts_of_day
from lib.reminder_helper import get_reminder_provider, TIME_TRIGGER_METHOD, MOTION_TRIGGER_METHOD
from notifier import Notifier, Message, NotifierType


class Reminder(ConfigurableAutomation):

    def initialize(self):
        super().initialize()

        motion_entity_ids = self.cfg.list('motion_entity_id')
        self.init_trigger('state', {
            'entity_id': motion_entity_ids
        })
        self.init_handler(self.create_handler(
            [self.create_constraint('triggered_state', {
                'entity_id': motion_entity_ids,
                'to': 'on',
            })],
            [ReminderAction(self, self.args, MOTION_TRIGGER_METHOD)]))
        self.init_handler(self.create_handler(
            [self.create_constraint('triggered_state', {
                'entity_id': motion_entity_ids,
                'to': 'off',
            })],
            []))

        self.init_trigger('time', {
            'seconds': 60,
        })
        self.init_handler(self.create_handler([], [ReminderAction(self, self.args, TIME_TRIGGER_METHOD)]))


class ReminderAction(Action):
    def __init__(self, app, action_config, trigger_method):
        super().__init__(app, action_config)

        self.trigger_method = trigger_method
        self.providers = [get_reminder_provider(app, p) for p in self.cfg.list('providers', None)]
        self.provider_history = {}
        self.presence_mode_entity_id = self.cfg.value('presence_mode_entity_id', None)

    def do_action(self, trigger_info):
        if self.trigger_method == TIME_TRIGGER_METHOD and trigger_info.trigger_time.minute % 5:
            return

        motion_entity_id = trigger_info.data.get('entity_id')
        reminder_messages = self.get_reminder_messages()
        announcement_text = self.figure_announcement_text(reminder_messages)

        if not announcement_text:
            self.debug('No reminder message, skipping ...')
            return

        use_cache = True if len(announcement_text) < 100 else False
        announcer: Announcer = self.app.get_app('announcer')
        announcer.announce(announcement_text, use_cache=use_cache, motion_entity_id=motion_entity_id)

        notifier_text = self.figure_notifier_text(reminder_messages)
        if not notifier_text:
            return
        notifier: Notifier = self.app.get_app('notifier')
        notifier.notify(Message([NotifierType.IOS], 'all', None, notifier_text, None, {}))

    def get_reminder_messages(self):
        parts_of_day = figure_parts_of_day()
        presence_mode = self.get_state(self.presence_mode_entity_id)
        now = datetime.now()
        reminder_messages = []

        for provider in self.providers:
            if not provider.enabled:
                continue

            last_runtime = self.provider_history.get(provider)
            context = Context(parts_of_day, presence_mode=presence_mode, last_trigger_time=last_runtime)

            if not self.should_check_provider(context, provider, now):
                continue

            try:
                reminder_message = provider.provide(context)
                if reminder_message is not None:
                    reminder_messages.append(reminder_message)
                    self.provider_history[provider] = now
            except:
                self.app.error("Unable to get reminder text: {}".format(traceback.format_exc()))

        return reminder_messages

    def figure_announcement_text(self, reminder_messages):
        if not reminder_messages:
            return
        reminder_texts = [message.announcement_text for message in reminder_messages]
        text = MEDIUM_PAUSE.join(reminder_texts)

        self.debug('Built reminder announcement text: {}'.format(text))

        return text

    def figure_notifier_text(self, reminder_messages):
        if not reminder_messages:
            return
        notifier_texts = [message.notifier_text for message in reminder_messages if message.send_aggregated_notification]
        text = ' '.join(notifier_texts)

        self.debug('Built reminder notifier text: {}'.format(text))

        return text

    def should_check_provider(self, context, provider, now):
        if self.trigger_method != provider.trigger_method:
            self.debug('Skipping ... trigger_method ({} vs {}) not match'.format(self.trigger_method,
                                                                                 provider.trigger_method))
            return False

        last_runtime = context.last_trigger_time
        if last_runtime is None:
            return provider.can_provide(context)

        difference = (now - last_runtime).total_seconds() / 60
        if difference <= provider.interval:
            self.debug('Skipping ... min interval ({}) not reached'.format(provider.interval))
            return False

        return provider.can_provide(context)
