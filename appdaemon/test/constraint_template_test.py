import unittest
from unittest.mock import Mock, MagicMock

from constraints import get_constraint


def create_constraint(app, template, expected_value):
    return get_constraint(app, {
        'platform': 'template',
        'template': template,
        'expected_value': expected_value
    })


def expect_now_is_between(app, start_time, end_time):
    def side_effect(actual_start_time, actual_end_time):
        return start_time == actual_start_time and end_time == actual_end_time

    app.now_is_between = MagicMock(side_effect=side_effect)


def expect_state_values(app, expected_values):
    def side_effect(entity_id):
        return expected_values.get(entity_id)

    app.get_state = MagicMock(side_effect=side_effect)


class TestStateConstraint(unittest.TestCase):

    def test_numeric_state_value_match(self):
        app = Mock(**{'variables': {}})
        expect_state_values(app, {
            'sensor.master_bedroom': '23.2',
            'sensor.lynn_s_room': '22.1',
        })

        template = "{{ (state('sensor.master_bedroom') | float) - (state('sensor.lynn_s_room') | float) }}"

        constraint = create_constraint(app, template, ">1.0999999999999979")
        self.assertFalse(constraint.check(None))

        constraint = create_constraint(app, template, ">=1.0999999999999979")
        self.assertTrue(constraint.check(None))

        constraint = create_constraint(app, template, 1.0999999999999979)
        self.assertTrue(constraint.check(None))

        constraint = create_constraint(app, template, "<=1.0999999999999979")
        self.assertTrue(constraint.check(None))

        constraint = create_constraint(app, template, "<1.0999999999999979")
        self.assertFalse(constraint.check(None))

    def test_conditional_expected_value_match(self):
        app = Mock(**{'variables': {}})
        expect_state_values(app, {
            'sensor.master_bedroom': '23.2',
            'sensor.lynn_s_room': '22.1',
        })

        template = "{{ (state('sensor.master_bedroom') | float) - (state('sensor.lynn_s_room') | float) }}"
        expected_value = "{% if now_is_between('01:00:00', '06:30:00') %} >1 {% else %} >2 {% endif %}"

        expect_now_is_between(app, "01:00:00", "06:30:00")
        constraint = create_constraint(app, template, expected_value)
        self.assertTrue(constraint.check(None))

        expect_now_is_between(app, "00:00:00", "01:00:00")
        constraint = create_constraint(app, template, expected_value)
        self.assertFalse(constraint.check(None))
