from base_automation import BaseAutomation
from lib.actions import ServiceAction, LockAction
from lib.core.monitored_callback import monitored_callback

AUTO_LOCK_DELAY = 60 * 5


class AutoLock(BaseAutomation):

    def initialize(self):
        self._lock_entity_ids = self.cfg.list('lock_entity_id')
        self._control_entity_ids = self.cfg.list('control_entity_id')
        self._job_handle = None

        for entity_id in self._lock_entity_ids + self._control_entity_ids:
            self.debug('Registered {}'.format(entity_id))
            self.listen_state(self._state_change_handler, entity_id, immediate=True)

    @monitored_callback
    def _state_change_handler(self, entity, attribute, old, new, kwargs):
        self.log('state changed {} {}'.format(entity, new))
        if self._are_control_entities_off():
            return self._schedule_auto_lock()
        self._cancel_auto_lock()

    def _cancel_auto_lock(self):
        if self._job_handle is not None:
            self.cancel_timer(self._job_handle)
            self._job_handle = None

    def _schedule_auto_lock(self):
        self._cancel_auto_lock()
        self._job_handle = self.run_in(self._auto_lock_runner, AUTO_LOCK_DELAY)

    def _auto_lock_runner(self, kwargs={}):
        self._auto_lock()

    def _auto_lock(self):
        actions = []
        for entity_id in self._lock_entity_ids:
            state = self.get_state(entity_id)
            if state != 'locked':
                actions.append(LockAction(self, {
                    'entity_id': entity_id,
                }))

        if not actions:
            return

        self.do_actions(actions)

        # schedule auto lock job again to make sure we eventually lock the lock
        self._schedule_auto_lock()

    def _are_control_entities_off(self):
        for entity_id in self._control_entity_ids:
            state = self.get_state(entity_id)
            if state == 'on':
                self.debug('Not all control entities are off, entity_id={}'.format(entity_id))
                return False

        self.debug('All control entities are off')
        return True
