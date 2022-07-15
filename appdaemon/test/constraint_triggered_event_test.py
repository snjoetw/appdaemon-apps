import unittest
from unittest.mock import Mock

from constraints import get_constraint
from triggers import TriggerInfo


def create_constraint(config):
    app = Mock(**{'variables': {}})
    return get_constraint(app, {
        'platform': 'triggered_event',
        **config
    })


class TestTriggeredEventConstraint(unittest.TestCase):

    def test_value_exact_match(self):
        constraint = create_constraint({
            'event_name': 'ad.test_event',
            'event_data': {
                'event_type': 'package_left'
            }
        })
        result = constraint.check(TriggerInfo('event', {
            'event_name': 'ad.test_event',
            'data': {
                'event_type': 'package_left'
            }
        }))
        self.assertTrue(result)

    def test_value_not_match(self):
        constraint = create_constraint({
            'event_data': {
                'event_type': 'package_left'
            }
        })
        result = constraint.check(TriggerInfo('event', {
            'event_name': 'ad.test_event',
            'data': {
                'event_type': 'doorbell'
            }
        }))
        self.assertFalse(result)

    def test_value_in_list(self):
        constraint = create_constraint({
            'event_data': {
                'event_type': ['package_left', 'doorbell']
            }
        })
        result = constraint.check(TriggerInfo('event', {
            'event_name': 'ad.test_event',
            'data': {
                'event_type': 'package_left'
            }
        }))
        self.assertTrue(result)

    def test_value_not_in_list(self):
        constraint = create_constraint({
            'event_data': {
                'event_type': ['package_left', 'doorbell']
            }
        })
        result = constraint.check(TriggerInfo('event', {
            'event_name': 'ad.test_event',
            'data': {
                'event_type': 'motion'
            }
        }))
        self.assertFalse(result)
