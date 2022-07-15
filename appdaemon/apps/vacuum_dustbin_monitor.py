from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback
from lib.helper import to_int


def get_int_attribute(entity, attribute):
    value = get_attribute(entity, attribute)

    if value is None:
        return None

    return to_int(value)


def get_attribute(entity, attribute):
    if entity is None:
        return None

    if isinstance(entity, str):
        return None

    attributes = entity.get('attributes', {})
    return attributes.get(attribute)


def get_state(entity):
    if entity is None:
        return None

    if isinstance(entity, str):
        return entity

    return entity.get('state')


def diff(old, new):
    msg = 'Current: state={}, status={}\n'.format(get_state(new), get_attribute(new, 'status'))
    old_state = get_state(old)
    new_state = get_state(new)
    if old_state != new_state:
        msg = msg + 'state: {}->{}\n'.format(old_state, new_state)

    for attribute in ['status', 'battery_level']:
        old_attribute = get_attribute(old, attribute)
        new_attribute = get_attribute(new, attribute)
        if old_attribute != new_attribute:
            msg = msg + '{}: {}->{}\n'.format(attribute, old_attribute, new_attribute)

    return msg


# IDLE -> CLEANING
IDLE_STATE = 'IDLE'
# CLEANING -> CLEANING_COMPLETED, CLEANING_PAUSED_LOW_BATTERY
CLEANING_STATE = 'CLEANING'
# CLEANING_COMPLETED -> CHARGING
CLEANING_COMPLETED_STATE = 'CLEANING_COMPLETED'
# CLEANING_PAUSED_LOW_BATTERY -> CLEANING_PAUSED_CHARGING
CLEANING_PAUSED_LOW_BATTERY_STATE = 'CLEANING_PAUSED_LOW_BATTERY'
# CLEANING_PAUSED_CHARGING -> CLEANING
CLEANING_PAUSED_CHARGING_STATE = 'CLEANING_PAUSED_CHARGING'
# CHARGING -> IDLE, HEADING_DUMPING_AREA
CHARGING_STATE = 'CHARGING'
# HEADING_DUMPING_AREA -> AWAITING_DUSTBIN_REMOVAL_STATE
HEADING_DUMPING_AREA_STATE = 'HEADING_DUMPING_AREA'
# AWAITING_DUSTBIN_REMOVAL_STATE -> IDLE
AWAITING_DUSTBIN_REMOVAL_STATE = 'AWAITING_DUSTBIN_REMOVAL_STATE'


class VacuumDustbinMonitor(BaseAutomation):

    def initialize(self):
        self.cleaned_count_entity_id = self.cfg.value('runtime_entity_id')
        self.vacuum_entity_id = self.cfg.value('vacuum_entity_id')
        self.monitor_state_entity_id = self.cfg.value('monitor_state_entity_id')
        self.cleaned_count_threshold = self.cfg.value('cleaned_count_threshold', 100)
        self.dumping_spot_x_coord = self.cfg.value('dumping_spot_x_coord')
        self.dumping_spot_y_coord = self.cfg.value('dumping_spot_y_coord')
        self.vacuum_state_entity_id = self.cfg.value('vacuum_state_entity_id')

        self.listen_state(self.vacuum_state_change_handler, self.vacuum_entity_id, attribute="all")
        self.listen_state(self.vacuum_state_change_handler, "sensor.xiaomi_downstairs_vacuum_last_clean_area")
        self.listen_state(self.vacuum_state_change_handler, "sensor.xiaomi_downstairs_vacuum_current_clean_area")
        self.listen_state(self.vacuum_state_change_handler, "sensor.xiaomi_downstairs_vacuum_last_clean_start")
        self.listen_state(self.vacuum_state_change_handler, "sensor.xiaomi_downstairs_vacuum_last_clean_end")
        self.listen_state(self.vacuum_state_change_handler, "sensor.xiaomi_downstairs_vacuum_current_clean_duration")
        self.listen_state(self.vacuum_state_change_handler, "sensor.xiaomi_downstairs_vacuum_last_clean_duration")

    def handle_idle_state(self, old, new):
        old_state = get_state(old)
        new_state = get_state(new)

        if old_state != 'docked' or new_state != 'cleaning':
            self.debug('Unsupported vacuum_state, {}'.format(self.figure_state_debug_text(old, new)))
            return

        self.update_monitor_state(CLEANING_STATE)

    def handle_cleaning_state(self, old, new):
        old_state = get_state(old)
        new_state = get_state(new)

        if old_state != 'cleaning' or new_state != 'returning':
            self.debug('Unsupported vacuum_state, {}'.format(self.figure_state_debug_text(old, new)))
            return

        if self.is_attribute_changed(old, new, 'clean_start'):
            cleaned_area_count = to_int(self.get_state(self.cleaned_count_entity_id))
            cleaned_area_count = cleaned_area_count + get_int_attribute(new, 'cleaned_area')
            self.update_clean_count(cleaned_area_count)
            self.update_monitor_state(CLEANING_COMPLETED_STATE)
        else:
            self.update_monitor_state(CLEANING_PAUSED_LOW_BATTERY_STATE)

    def handle_cleaning_completed_state(self, old, new):
        old_state = get_state(old)
        new_state = get_state(new)

        if old_state != 'returning' or new_state != 'docked':
            self.debug('Unsupported vacuum_state, {}'.format(self.figure_state_debug_text(old, new)))
            return

        self.update_monitor_state(CHARGING_STATE)

    def handle_cleaning_paused_low_battery_state(self, old, new):
        old_state = get_state(old)
        new_state = get_state(new)

        if old_state != 'returning' or new_state != 'docked':
            self.debug('Unsupported vacuum_state, {}'.format(self.figure_state_debug_text(old, new)))
            return

        self.update_monitor_state(CLEANING_PAUSED_CHARGING_STATE)

    def handle_cleaning_paused_charging_state(self, old, new):
        old_state = get_state(old)
        new_state = get_state(new)

        if old_state != 'docked' or new_state != 'cleaning':
            self.debug('Unsupported vacuum_state, {}'.format(self.figure_state_debug_text(old, new)))
            return

        self.update_monitor_state(CLEANING_STATE)

    def handle_charging_state(self, old, new):
        if not self.is_attribute_changed(old, new, 'battery_level'):
            self.debug('Unsupported vacuum_state, {}'.format(self.figure_state_debug_text(old, new)))
            return

        battery_level = get_int_attribute(new, 'battery_level')
        if battery_level < 100:
            self.debug('Still charging, {}'.format(battery_level))
            return

        cleaned_area_count = to_int(self.get_state(self.cleaned_count_entity_id))
        if cleaned_area_count < self.cleaned_count_threshold:
            self.update_monitor_state(IDLE_STATE)
            return

        self.update_monitor_state(HEADING_DUMPING_AREA_STATE)
        self.go_to_dumping_area()

    def handle_heading_dumping_area_state(self, old, new):
        if not self.is_arrived_dumping_area(old, new):
            self.debug('Unsupported vacuum_state, {}'.format(self.figure_state_debug_text(old, new)))
            return

        self.update_monitor_state(AWAITING_DUSTBIN_REMOVAL_STATE)

    def handle_awaiting_dustbin_removal_state(self, old, new):
        state = get_state(new)
        if state != 'returning':
            self.debug('Unsupported vacuum_state, {}'.format(self.figure_state_debug_text(old, new)))
            return

        self.update_monitor_state(IDLE_STATE)
        self.update_clean_count(0)

    def figure_state_debug_text(self, old, new):
        old_state = get_state(old)
        new_state = get_state(new)
        return 'monitor_state={}, old_vacuum_state={}, new_vacuum_state={}, diff={}'.format(
            self.current_monitor_state(),
            old_state,
            new_state,
            diff(old, new))

    @monitored_callback
    def vacuum_state_change_handler(self, entity, attribute, old, new, kwargs):
        monitor_state = self.current_monitor_state()
        if monitor_state == CLEANING_STATE:
            self.handle_cleaning_state(old, new)
        elif monitor_state == CLEANING_COMPLETED_STATE:
            self.handle_cleaning_completed_state(old, new)
        elif monitor_state == CHARGING_STATE:
            self.handle_charging_state(old, new)
        elif monitor_state == CLEANING_PAUSED_LOW_BATTERY_STATE:
            self.handle_cleaning_paused_low_battery_state(old, new)
        elif monitor_state == CLEANING_PAUSED_CHARGING_STATE:
            self.handle_cleaning_paused_charging_state(old, new)
        elif monitor_state == HEADING_DUMPING_AREA_STATE:
            self.handle_heading_dumping_area_state(old, new)
        elif monitor_state == AWAITING_DUSTBIN_REMOVAL_STATE:
            self.handle_awaiting_dustbin_removal_state(old, new)
        elif monitor_state == IDLE_STATE:
            self.handle_idle_state(old, new)

    def is_state_changed(self, old, new):
        old_state = get_state(old)
        new_state = get_state(new)
        changed = old_state != new_state

        self.debug('State changed, {} => {}'.format(old_state, new_state))

        return changed

    def is_attribute_changed(self, old, new, attribute_name):
        old_attribute = get_attribute(old, attribute_name)
        new_attribute = get_attribute(new, attribute_name)

        if old_attribute is None or new_attribute is None:
            return False

        if old_attribute == new_attribute:
            return False

        self.debug('Attribute {} changed, {} => {}'.format(attribute_name, old_attribute, new_attribute))

        return True

    def is_arrived_dumping_area(self, old, new):
        old_state = get_state(old)
        new_state = get_state(new)
        if old_state != 'cleaning' or new_state != 'idle':
            self.debug('is_arrived_dumping_area => old_state ({}) NOT cleaning or new_state NOT idle ({})'.format(
                old_state, new_state))
            return False

        old_status = get_attribute(old, 'status')
        new_status = get_attribute(new, 'status')

        if old_status != 'Going to target' or new_status != 'Idle':
            self.debug('is_arrived_dumping_area => old_state ({}) NOT "Going to target" or new_state NOT Idle ({})'
                       .format(old_status, new_status))
            return False

        self.log('Arrived dumping area')

        return True

    def go_to_dumping_area(self):
        self.call_service(
            'xiaomi_miio/vacuum_goto',
            entity_id=self.vacuum_entity_id,
            x_coord=self.dumping_spot_x_coord,
            y_coord=self.dumping_spot_y_coord)

    def update_clean_count(self, count):
        self.call_service('input_number/set_value', entity_id=self.cleaned_count_entity_id, value=count)

    def update_monitor_state(self, state):
        self.select_option(self.monitor_state_entity_id, state)

    def current_monitor_state(self):
        return self.get_state(self.monitor_state_entity_id)
