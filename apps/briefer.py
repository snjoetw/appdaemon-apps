import traceback
from datetime import time
from enum import Enum

from announcer import Announcer
from configurable_automation import ConfigurableAutomation
from lib.actions import Action
from lib.briefing_helper import get_briefing_provider, MEDIUM_PAUSE
from lib.context import Context
from lib.core.monitored_callback import monitored_callback
from lib.helper import figure_parts_of_day


class Briefer(ConfigurableAutomation):

    def initialize(self):
        super().initialize()

        def briefing_text_provider():
            self.providers = [get_briefing_provider(self, p) for p in self.cfg.list('providers')]

            return self.build_briefing_text()

        self.init_trigger('state', {
            'entity_id': self.cfg.list('motion_entity_id'),
            'to': 'on',
        })
        self.init_trigger('state', {
            'entity_id': self.cfg.value('on_demand_entity_id'),
            'to': 'on',
        })

        handler = self.create_handler(
            [],
            [BrieferAnnouncementAction(self, self.args,
                                       briefing_text_provider)])
        self.init_handler(handler)

        self.enabler_entity_id = self.cfg.value('enabler_entity_id')
        self.briefing_state_entity_id = self.cfg.value('briefing_state_entity_id')
        midnight = time(0, 0, 0)
        self.run_daily(self.run_daily_handler, midnight)

    @monitored_callback
    def run_daily_handler(self, time=None, **kwargs):
        self.select_option(self.briefing_state_entity_id, BriefingState.EARLY_MORNING.name)

    def build_briefing_text(self):
        parts_of_day = figure_parts_of_day()
        context = Context(parts_of_day)

        briefing_texts = []
        for provider in self.providers:
            if not provider.can_brief(context):
                continue

            try:
                briefing_text = provider.briefing(context)
                if briefing_text is not None:
                    self.debug('Building briefing text with: {}'.format(
                        briefing_text))
                    briefing_texts.append(briefing_text)
            except:
                self.error("Unable to get briefing text: {}".format(
                    traceback.format_exc()))

        if len(briefing_texts) == 1:
            return

        return '<prosody rate="90%">{}</prosody>'.format(
            sanitize_briefing_text(MEDIUM_PAUSE.join(briefing_texts)))


class BrieferAnnouncementAction(Action):
    def __init__(self, app, action_config, message_provider):
        super().__init__(app, action_config)

        self.on_demand_entity_id = self.cfg.value('on_demand_entity_id', None)
        self.briefing_state_entity_id = self.cfg.value('briefing_state_entity_id', None)
        self.briefing_state_periods = self.cfg.value('briefing_state_period', None)
        self.message_provider = message_provider
        self.dry_run = self.cfg.value('dry_run', False)

    def do_action(self, trigger_info):
        should_brief = self.should_brief() or self.dry_run

        self.debug('should_brief={}'.format(should_brief))

        next_state = self.figure_next_briefing_state()
        self.select_option(self.briefing_state_entity_id, next_state.name)

        if not should_brief:
            return

        motion_entity_id = trigger_info.data.get('entity_id')
        if motion_entity_id == self.on_demand_entity_id:
            motion_entity_id = None

        message = self.message_provider()

        if not message:
            self.debug('No briefing message, skipping ...')
            return

        if self.dry_run:
            return

        self.app.sleep(2)

        announcer: Announcer = self.app.get_app('announcer')
        announcer.announce(message, use_cache=False, motion_entity_id=motion_entity_id)

    def should_brief(self):
        if self.get_state(self.on_demand_entity_id) == 'on':
            self.app.set_state(self.on_demand_entity_id, state='off')
            return True

        return self.is_in_current_state_period()

    def is_in_current_state_period(self):
        current_state = self.get_current_briefing_state()

        for p in self.briefing_state_periods:
            self.debug('Checking {} and {}'.format(p['state'], current_state.name))
            if p['state'] == current_state.name:
                return self.now.between(p['start_time'], p['end_time'])

        return False

    def figure_next_briefing_state(self):
        current_state = self.get_current_briefing_state()
        if current_state == BriefingState.NONE:
            return BriefingState.NONE

        periods_iterator = iter(self.briefing_state_periods)
        current_state_period = self.locate_current_briefing_state_period(periods_iterator, current_state)

        if current_state_period is None:
            return BriefingState.NONE

        if self.now.before(current_state_period['start_time']):
            self.debug('Next briefing state => period={} (current={})'.format(current_state_period, current_state))
            return current_state

        period = next(periods_iterator, None)
        while period is not None:
            self.debug('Checking period={}'.format(period))

            if self.now.before(period['end_time']):
                self.debug('Next briefing state => period={} (current={})'.format(period, current_state))
                return BriefingState[period['state']]

            period = next(periods_iterator, None)

        return BriefingState.NONE

    def locate_current_briefing_state_period(self, periods_iterator, current_state):
        period = next(periods_iterator, None)
        if period is None:
            return None

        if period['state'] == current_state.name:
            return period

        return self.locate_current_briefing_state_period(periods_iterator, current_state)

    def get_current_briefing_state(self):
        return BriefingState[self.get_state(self.briefing_state_entity_id)]


class BriefingState(Enum):
    EARLY_MORNING = 1
    MORNING = 2
    NOON = 3
    EVENING = 4
    NIGHT = 5
    WELCOME_BACK = 50
    NONE = 99


def sanitize_briefing_text(text):
    text = text.replace('&', ' and ')
    return text
