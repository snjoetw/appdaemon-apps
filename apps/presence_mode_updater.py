from configurable_automation import ConfigurableAutomation
from lib.actions import Action
from lib.presence_helper import HOME_PERSON_STATUSES, PERSON_STATUS_ARRIVING, \
    PERSON_STATUS_AWAY, PRESENCE_MODE_SOMEONE_IS_ARRIVING_HOME, \
    PRESENCE_MODE_SOMEONE_IS_HOME, PRESENCE_MODE_NO_ONE_IS_HOME, \
    PRESENCE_MODE_EVERYONE_IS_HOME


class PresenceModeUpdater(ConfigurableAutomation):

    def initialize(self):
        super().initialize()

        self.init_trigger('time', {
            'seconds': 120,
        })

        self.init_trigger('state', {
            'entity_ids': self.cfg.list('person_entity_id'),
        })

        handler = self.create_handler([], [UpdateAction(self, self.args)])
        self.init_handler(handler)


class UpdateAction(Action):
    def __init__(self, app, action_config):
        super().__init__(app, action_config)

        self.person_entity_ids = self.cfg.list('person_entity_id', None)
        self.presence_mode_entity_id = self.cfg.value('presence_mode_entity_id', None)

    def do_action(self, trigger_info):
        self.debug('About to determine presence mode for {}'.format(
            self.person_entity_ids))

        presence_mode = self.determine_presence_mode()

        self.debug('Updating presence mode ({}) to {}'.format(
            self.presence_mode_entity_id,
            presence_mode))

        if presence_mode is None:
            return

        current_mode = self.get_state(self.presence_mode_entity_id)

        if current_mode == presence_mode:
            return

        self.select_option(self.presence_mode_entity_id, presence_mode)

    def determine_presence_mode(self):
        number_of_people = len(self.person_entity_ids)
        home_people = []
        away_people = []
        arriving_people = []

        for person_entity_id in self.person_entity_ids:
            person_status = self.get_state(person_entity_id)

            if person_status in HOME_PERSON_STATUSES:
                home_people.append(person_entity_id)
            elif person_status == PERSON_STATUS_ARRIVING:
                arriving_people.append(person_entity_id)
            elif person_status == PERSON_STATUS_AWAY:
                away_people.append(person_entity_id)

        if len(home_people) == number_of_people:
            return PRESENCE_MODE_EVERYONE_IS_HOME
        elif len(away_people) == number_of_people:
            return PRESENCE_MODE_NO_ONE_IS_HOME
        elif len(home_people) > 0:
            return PRESENCE_MODE_SOMEONE_IS_HOME
        elif len(arriving_people) > 0:
            return PRESENCE_MODE_SOMEONE_IS_ARRIVING_HOME

        return None
