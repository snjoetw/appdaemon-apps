from collections import deque
from datetime import datetime

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback


class SequenceItem:
    def __init__(self, sequence_item_config):
        self._entity_id = sequence_item_config['entity_id']
        self._is_optional = sequence_item_config.get('optional', False)

    @property
    def entity_ids(self):
        if isinstance(self._entity_id, list):
            return self._entity_id
        return [self._entity_id]

    @property
    def is_optional(self):
        return self._is_optional

    def contains_entity_id(self, entity_id):
        return entity_id in self.entity_ids

    def __repr__(self):
        return "{}(entity_ids={})".format(
            self.__class__.__name__,
            self.entity_ids)


class QueuedItem:
    def __init__(self, sequence_item):
        self._sequence_item = sequence_item
        self._inserted_at = datetime.now()

    @property
    def sequence_item(self):
        return self._sequence_item

    @property
    def inserted_at(self):
        return self._inserted_at

    def __repr__(self):
        return "{}(sequence_item={}, inserted_at={})".format(
            self.__class__.__name__,
            self.sequence_item,
            self.inserted_at)


def _is_queue_item_too_old(queue_item):
    return (datetime.now() - queue_item.inserted_at).total_seconds() > 120


class SequenceMonitor(BaseAutomation):

    def initialize(self):
        self._min_match = self.cfg.value('min_match')
        self._sequence_entity_id = self.cfg.value('sequence_entity_id')
        self._queue = deque(maxlen=self._min_match)
        self._sequence_items = [SequenceItem(x) for x in self.cfg.list('sequence')]

        for sequence_item in self._sequence_items:
            for entity_id in sequence_item.entity_ids:
                self.debug('Registered listen_state callback for {}'.format(entity_id))
                self.listen_state(self._state_change_handler, entity_id, new='on')

    @monitored_callback
    def _state_change_handler(self, entity, attribute, old, new, kwargs):
        self.debug('state_change_handler triggered by {}'.format(entity))
        sequence_item = self.figure_sequence_item(entity)

        if self.is_sequence_item_queued_already(sequence_item):
            self.debug('Skipping {}, in_queue_already'.format(entity))
            return

        self._queue.append(QueuedItem(sequence_item))
        queued_items = self.queued_items
        self.log_sequence(queued_items)
        is_in_sequence = self.is_queued_items_in_sequence(queued_items)

        self.debug('is_in_sequence? {}'.format(is_in_sequence))

        if is_in_sequence:
            self.turn_on(self._sequence_entity_id)
        else:
            self.turn_off(self._sequence_entity_id)

    def is_sequence_item_queued_already(self, sequence_item):
        for queue_item in self.queued_items:
            if queue_item.sequence_item == sequence_item:
                return not _is_queue_item_too_old(queue_item)
        return False

    def figure_sequence_item(self, entity_id):
        for sequence_item in self._sequence_items:
            if sequence_item.contains_entity_id(entity_id):
                return sequence_item
        return None

    def is_queued_items_in_sequence(self, queued_items):
        if len(queued_items) < self._min_match:
            return False

        queued_item_itr = iter(queued_items)
        queued_item = next(queued_item_itr)

        for i, sequence_item in enumerate(self._sequence_items):
            if sequence_item == queued_item.sequence_item:
                matched = 1
                self.debug('Found first item => {}'.format(queued_item.sequence_item))
                i += 1
                while i < len(queued_items):
                    sequence_item = self._sequence_items[i]
                    queued_item = next(queued_item_itr)
                    if sequence_item != queued_item.sequence_item:
                        if sequence_item.is_optional:
                            self.debug('Skipping ... subsequent item NOT match but is optional => %s vs %s',
                                       sequence_item, queued_item.sequence_item)
                            break

                        self.debug('Subsequent item NOT match => %s vs %s', sequence_item, queued_item.sequence_item)
                        return False

                    matched += 1
                    self.debug('Found subsequent item => {}'.format(queued_item.sequence_item))
                    i += 1
                return matched >= self._min_match
        return False

    def log_sequence(self, queued_items):
        msg = 'Current Sequence:\n'
        for queue_item in queued_items:
            msg = msg + '  {}\n'.format(queue_item.sequence_item.entity_ids)
        return self.debug(msg)

    @property
    def queued_items(self):
        return [x for x in list(self._queue) if not _is_queue_item_too_old(x)]
