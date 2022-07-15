import re
from datetime import datetime, timedelta

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback


class LightRuntimeMonitor(BaseAutomation):
    def initialize(self):
        self._thresholds = self.cfg.value('thresholds')

        now = datetime.now() + timedelta(seconds=2)
        self.run_every(self._run_every_handler, now, self.cfg.value('check_frequency'))

    @monitored_callback
    def _run_every_handler(self, time=None, **kwargs):
        checked_entities = []

        for entity_id, entity in self.get_state().items():
            if entity is None:
                continue

            for config in self._thresholds:
                if re.match(config['entity_id'], entity_id):
                    if entity_id in checked_entities:
                        continue

                    checked_entities.append(entity_id)

                    if config.get('ignore', False):
                        continue

                    if self.runtime_exceeds_threshold(config, entity_id):
                        self.turn_off(entity_id)

    def runtime_exceeds_threshold(self, config, entity_id):
        runtime_in_sec = self.state_last_changed_duration(entity_id, 'on')
        if runtime_in_sec is None:
            return False

        runtime = runtime_in_sec / 60
        threshold = config['threshold_in_minute']

        self.debug('entity_id={}, runtime={}, threshold={}'.format(
            entity_id,
            runtime,
            threshold
        ))

        exceeds_threshold = runtime > threshold

        if exceeds_threshold:
            self.log('Runtime exceeds threshold, '
                     'entity_id={}, '
                     'threshold={}, '
                     'runtime={}'.format(entity_id,
                                         threshold,
                                         runtime))

        return exceeds_threshold
