import unittest
from unittest.mock import Mock

from constraints import get_constraint
from triggers import TriggerInfo


def create_constraint(config):
    app = Mock(**{'variables': {}})
    return get_constraint(app, {
        'platform': 'triggered_state',
        **config
    })


class TestTriggeredStateConstraint(unittest.TestCase):

    def test_entity_id_match(self):
        constraint = create_constraint({
            'entity_id': ['input_boolean.test', 'cover.garage']
        })
        result = constraint.check(TriggerInfo('state', {
            'entity_id': 'cover.garage'
        }))
        self.assertTrue(result)

    def test_entity_id_not_match(self):
        constraint = create_constraint({
            'entity_id': ['input_boolean.test', 'cover.garage']
        })
        result = constraint.check(TriggerInfo('state', {
            'entity_id': 'sensor.temperature'
        }))
        self.assertFalse(result)

    def test_attribute_match(self):
        constraint = create_constraint({
            'attribute': ['battery_level']
        })
        result = constraint.check(TriggerInfo('state', {
            'attribute': 'battery_level'
        }))
        self.assertTrue(result)

    def test_attribute_not_match(self):
        constraint = create_constraint({
            'attribute': ['battery_level']
        })
        result = constraint.check(TriggerInfo('state', {
            'attribute': 'temperature'
        }))
        self.assertFalse(result)

    def test_from_state_match(self):
        constraint = create_constraint({
            'from': ['open', 'opening']
        })
        result = constraint.check(TriggerInfo('state', {
            'from': 'open'
        }))
        self.assertTrue(result)

    def test_from_state_not_match(self):
        constraint = create_constraint({
            'from': ['open', 'opening']
        })
        result = constraint.check(TriggerInfo('state', {
            'from': 'closing'
        }))
        self.assertFalse(result)

    def test_to_state_match(self):
        constraint = create_constraint({
            'to': ['open', 'opening']
        })
        result = constraint.check(TriggerInfo('state', {
            'to': 'open'
        }))
        self.assertTrue(result)

    def test_to_state_not_match(self):
        constraint = create_constraint({
            'to': ['open', 'opening']
        })
        result = constraint.check(TriggerInfo('state', {
            'to': 'closing'
        }))
        self.assertFalse(result)
