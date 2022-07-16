from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback


class ClimatePresetModeOverrider(BaseAutomation):
    overrides: dict
    override_enabler_entity_id: str
    climate_entity_id: list

    def initialize(self):
        self.climate_entity_id = self.args.get('climate_entity_id')
        self.override_enabler_entity_id = self.args.get('override_enabler_entity_id')
        self.overrides = self.args.get('overrides')

        self.listen_state(self.preset_change_handler, self.climate_entity_id, attribute='preset_mode')
        self.listen_state(self.override_state_change_handler, self.override_enabler_entity_id)

    @monitored_callback
    def preset_change_handler(self, entity, attribute, old, new, kwargs):
        if self.get_state(self.override_enabler_entity_id) != 'on':
            self.debug('Skipping, override preset not enabled with {}'.format(self.override_enabler_entity_id))
            return

        self.override_preset_mode(new)

    @monitored_callback
    def override_state_change_handler(self, entity, attribute, old, new, kwargs):
        current_preset_modes = self.get_state(self.climate_entity_id, attribute='preset_mode')
        if self.get_state(self.override_enabler_entity_id) == 'on':
            self.override_preset_mode(current_preset_modes)
        else:
            self.rollback_preset_mode(current_preset_modes)

    def override_preset_mode(self, preset_mode):
        overridden_mode = self.overrides.get(preset_mode)

        if overridden_mode is None:
            self.debug('Skipping, no overridden mode defined for {}'.format(preset_mode))
            return

        possible_modes = self.get_state(self.climate_entity_id, attribute='preset_modes')
        if overridden_mode not in possible_modes:
            self.error('Skipping, {} is not in possible modes: {}'.format(overridden_mode, possible_modes))
            return

        self.set_preset_mode(overridden_mode)

    def rollback_preset_mode(self, preset_mode):
        for original, override in self.overrides.items():
            if preset_mode == override:
                self.debug('Rolling back preset mode from {} to {}'.format(preset_mode, original))
                self.set_preset_mode(original)
                return

    def set_preset_mode(self, preset_mode):
        self.call_service('climate/set_preset_mode', entity_id=self.climate_entity_id, preset_mode=preset_mode)
