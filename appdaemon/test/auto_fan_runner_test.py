import pytest

from auto_fan_runner import AutoFanRunner
from presence_helper import PRESENCE_MODE_NO_ONE_IS_HOME, \
    PRESENCE_MODE_SOMEONE_IS_HOME

OFFICE_CONFIG = {
    'temperature_entity_id': 'sensor.office_temperature',
    'fan_entity_id': 'fan.office_fan',
    'fan_on_temperature_offset': '-0.1',
    'fan_off_temperature_offset': '-0.3',
    'ignore_presence_mode': False,
    'enabler_entity_id': 'input_boolean.is_office_enabled',
}

KITCHEN_CONFIG = {
    'temperature_entity_id': 'sensor.kitchen_temperature',
    'fan_entity_id': 'climate.kitchen_fan',
    'temperature_high_offset': '-0.3',
    'temperature_low_offset': '-0.1',
    'ignore_presence_mode': False,
    'enabler_entity_id': 'input_boolean.is_kitchen_enabled',
}


def common_passed_args(given_that):
    given_that.passed_arg('climate_entity_id').is_set_to('climate.main_floor')
    given_that.passed_arg('presence_mode_entity_id').is_set_to(
        'input_select.presence_mode')
    given_that.passed_arg('monitors').is_set_to([
        OFFICE_CONFIG,
        KITCHEN_CONFIG
    ])


@pytest.fixture
def auto_fan_runner(given_that, hass_functions):
    given_that.mock_functions_are_cleared()

    common_passed_args(given_that)

    auto_fan_runner = AutoFanRunner(None, None, None, None, None, None, None,
                                    None)
    auto_fan_runner.initialize()

    return auto_fan_runner


def test_should_turn_on_fan_when_current_temperature_is_over_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)
    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'on')
    expect_fan_state(given_that, 'fan.office_fan', 'off')

    expect_temperature(given_that, 'sensor.office_temperature', 26)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_on').was.called_with(
        entity_id='fan.office_fan'
    )


def test_should_not_turn_on_fan_when_current_temperature_is_over_threshold_and_enabler_is_off(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)
    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'off')
    expect_fan_state(given_that, 'fan.office_fan', 'off')

    expect_temperature(given_that, 'sensor.office_temperature', 26)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_on').was_not.called_with(
        entity_id='fan.office_fan'
    )


def test_should_not_turn_on_fan_when_current_temperature_is_over_threshold_and_no_one_is_home(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)
    expect_presence_mode(given_that, PRESENCE_MODE_NO_ONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'on')
    expect_fan_state(given_that, 'fan.office_fan', 'off')

    expect_temperature(given_that, 'sensor.office_temperature', 26)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_on').was_not.called_with(
        entity_id='fan.office_fan'
    )


def test_should_not_turn_on_fan_when_current_temperature_is_over_threshold_and_fan_is_already_running(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)
    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'on')
    expect_fan_state(given_that, 'fan.office_fan', 'on')

    expect_temperature(given_that, 'sensor.office_temperature', 26)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_on').was_not.called_with(
        entity_id='fan.office_fan'
    )


def test_should_not_turn_on_fan_when_current_temperature_is_below_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)
    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'on')
    expect_fan_state(given_that, 'fan.office_fan', 'off')

    expect_temperature(given_that, 'sensor.office_temperature', 25.9)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_on').was_not.called_with(
        entity_id='fan.office_fan'
    )


def test_should_turn_off_fan_when_current_temperature_is_below_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'on')
    expect_fan_state(given_that, 'fan.office_fan', 'on')

    expect_temperature(given_that, 'sensor.office_temperature', 25.6)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_off').was.called_with(
        entity_id='fan.office_fan'
    )


def test_should_turn_off_fan_when_current_temperature_is_below_threshold_and_no_one_is_home(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_NO_ONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'on')
    expect_fan_state(given_that, 'fan.office_fan', 'on')

    expect_temperature(given_that, 'sensor.office_temperature', 25.6)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_off').was.called_with(
        entity_id='fan.office_fan'
    )


def test_should_not_turn_off_fan_when_current_temperature_is_below_threshold_and_enabler_is_off(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'off')
    expect_fan_state(given_that, 'fan.office_fan', 'on')

    expect_temperature(given_that, 'sensor.office_temperature', 25.6)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_off').was_not.called_with(
        entity_id='fan.office_fan'
    )


def test_should_not_turn_off_fan_when_current_temperature_is_above_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'on')
    expect_fan_state(given_that, 'fan.office_fan', 'on')

    expect_temperature(given_that, 'sensor.office_temperature', 25.7)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_off').was_not.called_with(
        entity_id='fan.office_fan'
    )


def test_should_not_turn_off_fan_when_current_temperature_is_below_threshold_and_fan_is_already_off(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_office_enabled', 'on')
    expect_fan_state(given_that, 'fan.office_fan', 'off')

    expect_temperature(given_that, 'sensor.office_temperature', 25.6)
    auto_fan_runner.check(OFFICE_CONFIG)

    assert_that('fan/turn_off').was_not.called_with(
        entity_id='fan.office_fan'
    )


def test_should_turn_on_climate_fan_when_current_temperature_is_below_low_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_kitchen_enabled', 'on')
    expect_fan_state(given_that, 'climate.kitchen_fan', 'off')

    expect_temperature(given_that, 'sensor.kitchen_temperature', 21.8)
    auto_fan_runner.check(KITCHEN_CONFIG)

    assert_that('climate/turn_on').was.called_with(
        entity_id='climate.kitchen_fan'
    )


def test_should_not_turn_on_climate_fan_when_current_temperature_is_above_low_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_kitchen_enabled', 'on')
    expect_fan_state(given_that, 'climate.kitchen_fan', 'off')

    expect_temperature(given_that, 'sensor.kitchen_temperature', 21.9)
    auto_fan_runner.check(KITCHEN_CONFIG)

    assert_that('climate/turn_on').was_not.called_with(
        entity_id='climate.kitchen_fan'
    )


def test_should_turn_on_climate_fan_when_current_temperature_is_above_high_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_kitchen_enabled', 'on')
    expect_fan_state(given_that, 'climate.kitchen_fan', 'off')

    expect_temperature(given_that, 'sensor.kitchen_temperature', 25.8)
    auto_fan_runner.check(KITCHEN_CONFIG)

    assert_that('climate/turn_on').was.called_with(
        entity_id='climate.kitchen_fan'
    )


def test_should_not_turn_on_climate_fan_when_current_temperature_is_below_high_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_kitchen_enabled', 'on')
    expect_fan_state(given_that, 'climate.kitchen_fan', 'off')

    expect_temperature(given_that, 'sensor.kitchen_temperature', 25.7)
    auto_fan_runner.check(KITCHEN_CONFIG)

    assert_that('climate/turn_on').was_not.called_with(
        entity_id='climate.kitchen_fan'
    )


def test_should_not_turn_on_climate_fan_when_current_temperature_is_above_high_threshold_and_fan_is_already_on(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_kitchen_enabled', 'on')
    expect_fan_state(given_that, 'climate.kitchen_fan', 'on')

    expect_temperature(given_that, 'sensor.kitchen_temperature', 25.8)
    auto_fan_runner.check(KITCHEN_CONFIG)

    assert_that('climate/turn_on').was_not.called_with(
        entity_id='climate.kitchen_fan'
    )


def test_should_turn_off_climate_fan_when_current_temperature_is_within_threshold(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_kitchen_enabled', 'on')
    expect_fan_state(given_that, 'climate.kitchen_fan', 'on')

    expect_temperature(given_that, 'sensor.kitchen_temperature', 25.6)
    auto_fan_runner.check(KITCHEN_CONFIG)

    assert_that('climate/turn_off').was.called_with(
        entity_id='climate.kitchen_fan'
    )


def test_should_not_turn_off_climate_fan_when_current_temperature_is_within_threshold_and_fan_is_already_off(
        given_that,
        auto_fan_runner,
        assert_that):
    expect_climate_state(given_that, 26, 22)

    expect_presence_mode(given_that, PRESENCE_MODE_SOMEONE_IS_HOME)
    expect_enabler(given_that, 'input_boolean.is_kitchen_enabled', 'on')
    expect_fan_state(given_that, 'climate.kitchen_fan', 'off')

    expect_temperature(given_that, 'sensor.kitchen_temperature', 25.6)
    auto_fan_runner.check(KITCHEN_CONFIG)

    assert_that('climate/turn_off').was_not.called_with(
        entity_id='climate.kitchen_fan'
    )


def expect_climate_state(given_that, high, low):
    given_that.state_of('climate.main_floor').is_set_to('auto', {
        'state': 'auto',
        'attributes': {
            'target_temp_high': high,
            'target_temp_low': low,
        }
    })


def expect_presence_mode(given_that, presence_mode):
    given_that.state_of('input_select.presence_mode').is_set_to(presence_mode)


def expect_enabler(given_that, enabler_entity_id, enabled):
    given_that.state_of(enabler_entity_id).is_set_to(enabled)


def expect_temperature(given_that, temperature_entity_id, temperature):
    given_that.state_of(temperature_entity_id).is_set_to(temperature)


def expect_fan_state(given_that, fan_entity_id, state):
    given_that.state_of(fan_entity_id).is_set_to(state)
