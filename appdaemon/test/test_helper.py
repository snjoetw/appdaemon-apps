from datetime import datetime

from pytz import timezone

from triggers import TriggerInfo


def create_state_trigger_info(triggered_entity_id, **kwargs):
    return TriggerInfo('state', data={
        **kwargs,
        'entity_id': triggered_entity_id,
    })


def create_time_trigger_info(**kwargs):
    return TriggerInfo('time', data={
        **kwargs,
    })


def now_is_between(hass_functions, start, end):
    def now_is_between_mock(_start, _end):
        return _start == start and _end == end

    hass_functions['now_is_between'].side_effect = now_is_between_mock


def create_datetime(year, month, day, hour, minute, second, tzinfo=timezone('US/Pacific')):
    return datetime(year, month, day, hour, minute, second, tzinfo=tzinfo)
