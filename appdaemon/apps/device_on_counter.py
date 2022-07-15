from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback


class DeviceOnCounter(BaseAutomation):
    def initialize(self):
        self.counter_entity_id = self.cfg.list('counter_entity_id')
        self.device_entity_ids = self.cfg.list('device_entity_id')
        self.device_on_state = self.cfg.value('device_on_state', 'on')
        for device_entity_id in self.device_entity_ids:
            self.listen_state(self._state_change_handler, device_entity_id)

    @monitored_callback
    def _state_change_handler(self, entity, attribute, old, new, kwargs):
        count = 0

        for device_entity_id in self.device_entity_ids:
            if self.get_state(device_entity_id) == self.device_on_state:
                count = count + 1

        self.call_service('input_number/set_value',
                          entity_id=self.counter_entity_id,
                          value=count)
