import unittest
from unittest.mock import Mock

from constraints import get_constraint
from triggers import TriggerInfo


def create_constraint(expected_state, actual_state, variables={}):
    app = Mock(**{'get_state.return_value': actual_state})
    app.variables = variables
    return get_constraint(app, {
        'platform': 'state',
        'entity_id': 'input_number.test',
        'state': expected_state
    })


class TestStateConstraint(unittest.TestCase):

    def test_numeric_state_value_match(self):
        constraint = create_constraint(11, 11)
        result = constraint.check(TriggerInfo('state'))
        self.assertTrue(result)

    def test_numeric_state_value_not_match(self):
        constraint = create_constraint(11, 12)
        result = constraint.check(TriggerInfo('state'))
        self.assertFalse(result)

    def test_string_state_value_match(self):
        constraint = create_constraint('Open', 'Open')
        result = constraint.check(TriggerInfo('state'))
        self.assertTrue(result)

    def test_string_state_value_not_match(self):
        constraint = create_constraint('Open', 'Close')
        result = constraint.check(TriggerInfo('state'))
        self.assertFalse(result)

    def test_state_with_greater_or_equal_operator_value_match(self):
        constraint = create_constraint('>=11', 11)
        result = constraint.check(TriggerInfo('state'))
        self.assertTrue(result)

    def test_state_with_greater_or_equal_operator_value_not_match(self):
        constraint = create_constraint('>=11', 10)
        result = constraint.check(TriggerInfo('state'))
        self.assertFalse(result)

    def test_state_with_greater_operator_value_match(self):
        constraint = create_constraint('>11', 12)
        result = constraint.check(TriggerInfo('state'))
        self.assertTrue(result)

    def test_state_with_greater_operator_value_not_match(self):
        constraint = create_constraint('>11', 11)
        result = constraint.check(TriggerInfo('state'))
        self.assertFalse(result)

    def test_state_with_less_or_equal_operator(self):
        # VALUE MATCH
        result = create_constraint('<=11', 11).check(TriggerInfo('state'))
        self.assertTrue(result)

        result = create_constraint('<=11.0', 11).check(TriggerInfo('state'))
        self.assertTrue(result)

        result = create_constraint('<=11', 10.99).check(TriggerInfo('state'))
        self.assertTrue(result)

        # VALUE NOT MATCH
        result = create_constraint('<=11', 12).check(TriggerInfo('state'))
        self.assertFalse(result)

        result = create_constraint('<=11', 11.1).check(TriggerInfo('state'))
        self.assertFalse(result)

    def test_state_with_less_operator(self):
        # VALUE MATCH
        result = create_constraint('<11', 10).check(TriggerInfo('state'))
        self.assertTrue(result)

        result = create_constraint('<0.8', 0.4).check(TriggerInfo('state'))
        self.assertTrue(result)

        result = create_constraint('<1.2', 1).check(TriggerInfo('state'))
        self.assertTrue(result)

        result = create_constraint('<{{amp_threshold}}', 0.4, {'amp_threshold': 0.8}).check(TriggerInfo('state'))
        self.assertTrue(result)

        # VALUE NOT MATCH
        result = create_constraint('<11', 11).check(TriggerInfo('state'))
        self.assertFalse(result)

        result = create_constraint('<11', 11.1).check(TriggerInfo('state'))
        self.assertFalse(result)

        result = create_constraint('<{{amp_threshold}}', 0.88, {'amp_threshold': 0.8}).check(TriggerInfo('state'))
        self.assertFalse(result)

        result = create_constraint('<{{amp_threshold}}', None, {'amp_threshold': 0.8}).check(TriggerInfo('state'))
        self.assertFalse(result)

    def test_state_list_match(self):
        constraint = create_constraint(['open', 'opening'], 'open')
        result = constraint.check(TriggerInfo('state'))
        self.assertTrue(result)

    def test_state_list_not_match(self):
        constraint = create_constraint(['open', 'opening'], 'closing')
        result = constraint.check(TriggerInfo('state'))
        self.assertFalse(result)
