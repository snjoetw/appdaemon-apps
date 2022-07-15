from base_automation import BaseAutomation
from lib.actions import ServiceAction, TurnOnAction, TurnOffAction
from lib.core.monitored_callback import monitored_callback

LED_SERVICE_CALLS = {
    'switch_led_on': 'tplink/switch_set_led_on',
    'switch_led_off': 'tplink/switch_set_led_off',
    'light_led_on': 'tplink/light_set_led_on',
    'light_led_off': 'tplink/light_set_led_off',
}

LED_ACTION_DELAY = 30


class KasaLedMonitor(BaseAutomation):

    def initialize(self):
        self._enabler_entity_id = self.cfg.value('enabler_entity_id')
        self._kasa_entity_ids = self.cfg.list('kasa_entity_id')
        self._control_entity_ids = self.cfg.list('control_entity_id')
        self._scheduled_handle = None

        for entity_id in self._kasa_entity_ids + self._control_entity_ids:
            self.debug('Registered {}'.format(entity_id))
            self.listen_state(self._state_change_handler, entity_id, immediate=True)

        self.listen_state(self._state_change_handler, self._enabler_entity_id, immediate=True)

    @monitored_callback
    def _state_change_handler(self, entity, attribute, old, new, kwargs):
        self.log('state changed {} {}'.format(entity, new))
        if self.get_state(self._enabler_entity_id) == 'off':
            self._set_led(False)
            return

        if self._are_control_entities_off():
            return self._schedule_led_off()

        self._set_led(True)

    def _schedule_led_on(self):
        self._scheduled_handle = self.run_in(self._delayed_led_action_runner, LED_ACTION_DELAY, turn_on_led=True)

    def _schedule_led_off(self):
        self._scheduled_handle = self.run_in(self._delayed_led_action_runner, LED_ACTION_DELAY, turn_on_led=False)

    def _delayed_led_action_runner(self, kwargs={}):
        turn_on_led = kwargs.get('turn_on_led')
        self._set_led(turn_on_led)

    def _set_led(self, turn_on_led):
        if self._scheduled_handle:
            self.cancel_timer(self._scheduled_handle)
            self._scheduled_handle = None

        self.debug('About to set led, turn_on_led={}'.format(turn_on_led))
        actions = []
        for entity_id in self._kasa_entity_ids:
            led_on = self.get_state(entity_id)
            if led_on != turn_on_led:
                if turn_on_led:
                    actions.append(TurnOnAction(self, {'entity_ids': entity_id}))
                else:
                    actions.append(TurnOffAction(self, {'entity_ids': entity_id}))

        if not actions:
            return

        self.do_actions(actions)

        if not turn_on_led and self._are_kasa_led_on():
            self._schedule_led_off()
        elif turn_on_led and not self._are_kasa_led_on():
            self._schedule_led_on()

    def _are_kasa_led_on(self):
        for entity_id in self._kasa_entity_ids:
            led_on = self.get_state(entity_id)
            if led_on == 'on':
                return True
        return False

    def _are_control_entities_off(self):
        for entity_id in self._control_entity_ids:
            if self.get_state(entity_id) == 'on':
                self.debug('Not all control entities are off, entity_id={}'.format(entity_id))
                return False

        self.debug('All control entities are off')
        return True
