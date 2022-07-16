from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback


class VacuumCleaner(BaseAutomation):
    _area_configs: dict
    _vacuum_entity_id: str

    def initialize(self):
        self._area_configs = self.cfg.value('areas')
        self._vacuum_entity_id = self.cfg.value('vacuum_entity_id')

        self.listen_event(self._webhook_handler, 'ifttt_webhook_received', action='vacuum')

    @monitored_callback
    def _webhook_handler(self, event_name, data, kwargs):
        target_area = data.get('area')
        segment_ids = [segment_id for area_name, segment_id in self._area_configs.items() if area_name in target_area]

        if not segment_ids:
            self.log('No matching area found: {}'.format(target_area))
            return

        self.call_service('xiaomi_miio/vacuum_clean_segment', **{
            'entity_id': self._vacuum_entity_id,
            'segments': segment_ids,
        })
