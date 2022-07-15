from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback

HOME_ZONE = "home"
AWAY = "not_home"

MESSAGE_LEFT_ZONE = "{} left {}"
MESSAGE_ARRIVED_ZONE = "{} arrived {}"


class ZoneChangeNotificationAutomation(BaseAutomation):
    def initialize(self):
        # args
        self.device_entity_ids = self.cfg.value("device_entity_ids")
        self.notify_entity_ids = self.cfg.value("notify_entity_ids")

        for device in self.device_entity_ids:
            self.listen_state(self.device_state_change_handler, device)

    @monitored_callback
    def device_state_change_handler(self, entity, attribute, old, new, kwargs):
        if old != AWAY and new == AWAY:
            self.log("{} left {}".format(entity, old))

            self.person_left_zone(entity, old)
        elif old == AWAY and new != AWAY:
            self.log("{} arrived {}".format(entity, new))

            self.person_arrived_zone(entity, new)

    def person_left_zone(self, person_entity_id, zone):
        person = self.get_state(person_entity_id, attribute="friendly_name")
        data = {}

        if zone == HOME_ZONE:
            data["push"] = {
                "category": "left_home"
            }

        self.notify(MESSAGE_LEFT_ZONE.format(person, zone.lower()), data)

    def person_arrived_zone(self, person_entity_id, zone):
        person = self.get_state(person_entity_id, attribute="friendly_name")
        data = {}

        if zone == HOME_ZONE:
            data["push"] = {
                "category": "arrived_home"
            }

        person = person.replace('\'s iPhone', '').replace('\'s iPad', '')

        self.notify(MESSAGE_ARRIVED_ZONE.format(person, zone.lower()), data)

    def notify(self, message, data):
        for notify_entity_id in self.notify_entity_ids:
            self.call_service("notify/{}".format(notify_entity_id),
                              message=message, data=data)
