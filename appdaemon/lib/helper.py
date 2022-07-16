from collections.abc import MutableMapping
from datetime import datetime

from lib.context import PartsOfDay


OCCUPANCY_UNKNOWN = 'UNKNOWN'
OCCUPANCY_OCCUPIED = 'OCCUPIED'
OCCUPANCY_UNOCCUPIED = 'UNOCCUPIED'

STATE_ON = 'on'
STATE_OFF = 'off'
STATE_PLAYING = 'playing'
STATE_ARMED_AWAY = 'armed_away'
STATE_ARMED_HOME = 'armed_home'

def list_value(value, default=[]):
    if value is None:
        return default

    if isinstance(value, list):
        return _flatten_list_arg(value)

    return [value]


def _flatten_list_arg(arg_value):
    values = []
    for value in arg_value:
        if isinstance(value, list):
            values.extend(_flatten_list_arg(value))
        else:
            values.append(value)

    return values


def is_int(raw):
    try:
        value = to_int(raw)
        return value is not None
    except ValueError:
        return False
    except TypeError as e:
        raise Exception('Invalid value: {}'.format(raw)) from e


def is_float(raw):
    try:
        value = to_float(raw)
        return value is not None
    except ValueError:
        return False
    except TypeError as e:
        raise Exception('Invalid value: {}'.format(raw)) from e


def to_int(raw, default_value=None):
    if raw is None:
        return default_value

    converted = to_float(raw, default_value)
    if converted is None:
        return default_value

    return int(round(converted))


def to_float(raw, default_value=None):
    if raw is None:
        return default_value

    try:
        return float(raw)
    except ValueError:
        return default_value


def to_boolean(raw, default_value=False):
    if raw is None:
        return default_value

    if isinstance(raw, bool):
        return raw
    elif isinstance(raw, (float, int)):
        return raw > 0
    elif isinstance(raw, str):
        return raw in ('true', 'True', 'on', '1')


def create_ios_push_data(category, entity_id=None, action_data=None, attachment=None):
    data = {
        'push': {
            'category': category
        },
    }

    if entity_id is not None:
        data['entity_id'] = entity_id

    if action_data is not None:
        data['action_data'] = action_data

    if attachment is not None:
        data['attachment'] = attachment

    return data


def concat_list(items, concat_str=', ', sort=True):
    if not items:
        return None

    length = len(items)
    if length == 1:
        return items[0]

    if sort:
        items = sorted(items)

    return concat_str.join(items[:-1]) + " and " + str(items[-1])


def figure_parts_of_day():
    now = datetime.now()
    if today_at(4, 0) <= now < today_at(12, 0):
        return PartsOfDay.MORNING
    elif today_at(12, 0) <= now < today_at(17, 0):
        return PartsOfDay.AFTERNOON
    elif today_at(17, 0) <= now < today_at(20, 0):
        return PartsOfDay.EVENING
    else:
        return PartsOfDay.NIGHT


def today_at(hour, minute):
    return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)


def to_datetime(raw):
    if raw is None:
        return None

    if len(raw) == 32:
        # 2019-12-02T19:02:07.776968+00:00
        raw = raw[::-1].replace(':', '', 1)[::-1]
        return datetime.strptime(raw, '%Y-%m-%dT%H:%M:%S.%f%z')

    return None


def to_date(raw):
    if raw is None:
        return None
    return datetime.strptime(raw, '%Y-%m-%d')


def to_time(raw):
    return datetime.strptime(raw, '%H:%M:%S').time()


def flatten_dict(d, parent_key=''):
    sep = '.'
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_dict(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)
