from base_automation import BaseAutomation
from lib.presence_helper import PRESENCE_MODE_NO_ONE_IS_HOME
from notifier import NotifierType, Message, Notifier


class AlarmNotifier(BaseAutomation):
    _entity_settings: dict
    _presence_mode_entity_id: str
    _is_vacation_mode_entity_id: str

    def initialize(self):
        self._is_vacation_mode_entity_id = self.cfg.value('is_vacation_mode_entity_id')
        self._presence_mode_entity_id = self.cfg.value('presence_mode_entity_id')
        self._entity_settings = self.cfg.value('entity_settings')

    def notify(self, notifiers: list, title: str, message: str, trigger_entity_id: str, image_filename: str = None,
               settings: dict = {}):
        notifier_types = self._figure_notifier_types(notifiers)
        camera_entity_id = self._figure_camera_entity_id(trigger_entity_id)

        notifier: Notifier = self.get_app('notifier')
        notifier.notify(Message(notifier_types, 'all', title, message, camera_entity_id, settings))

    def _figure_camera_entity_id(self, trigger_entity_id):
        setting = self._entity_settings.get(trigger_entity_id, {})
        camera_entity_id = setting.get('camera_entity_id')

        self.debug('trigger_entity_id={} => camera_entity_id={}'.format(trigger_entity_id, camera_entity_id))

        return camera_entity_id

    def _figure_notifier_types(self, notifier_types):
        if notifier_types:
            return notifier_types

        notifiers = [NotifierType.PERSISTENT_NOTIFICATION, NotifierType.IOS]
        is_vacation_mode = self.get_state(self._is_vacation_mode_entity_id)
        presence_mode = self.get_state(self._presence_mode_entity_id)
        if is_vacation_mode == 'on' and presence_mode == PRESENCE_MODE_NO_ONE_IS_HOME:
            notifiers.append(NotifierType.FACEBOOK_MESSENGER)

        return notifiers
