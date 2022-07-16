from datetime import timedelta, datetime
from types import MethodType

import pytest

from motion_lighting import MotionLighting
from test.test_helper import create_state_trigger_info, \
    create_time_trigger_info, now_is_between


def common_passed_args(given_that):
    given_that.passed_arg('enabler_entity_id').is_set_to(
        'input_boolean.is_motion_enabled')
    given_that.passed_arg('lighting_mode_entity_id').is_set_to(
        'input_select.lighting_mode')
    given_that.passed_arg('motion_entity_id').is_set_to([
        'binary_sensor.motion',
        'binary_sensor.motion_2',
    ])
    given_that.passed_arg('turn_off_delay').is_set_to(30)
    given_that.passed_arg('dim_light_before_turn_off').is_set_to(True)
    given_that.passed_arg('lighting_modes').is_set_to(
        {
            'Dark': [
                {
                    'entity_id': 'light.office_light',
                    'brightness': 200,
                    'force_on': False,
                    'force_off': False,
                },
                'switch.tv'
            ]
        })
    given_that.passed_arg('turn_on_constraints').is_set_to([])
    given_that.passed_arg('turn_on_start_time').is_set_to(None)
    given_that.passed_arg('turn_on_end_time').is_set_to(None)
    given_that.passed_arg('image_processing').is_set_to(None)


@pytest.fixture
def motion_lighting(given_that, hass_functions):
    given_that.mock_functions_are_cleared()

    common_passed_args(given_that)

    motion_lighting = create_motion_lighting_app()

    return motion_lighting


@pytest.fixture
def motion_lighting_with_turn_on_time(given_that, hass_functions):
    given_that.mock_functions_are_cleared()

    common_passed_args(given_that)
    given_that.passed_arg('turn_on_start_time').is_set_to('16:00:00')
    given_that.passed_arg('turn_on_end_time').is_set_to('21:00:00')

    motion_lighting = create_motion_lighting_app()

    return motion_lighting


@pytest.fixture
def motion_lighting_with_image_processing(given_that, hass_functions):
    given_that.mock_functions_are_cleared()

    common_passed_args(given_that)
    given_that.passed_arg('image_processing').is_set_to({
        'entity_id': 'image_processing.entity_id',
        'enabler_entity_id': 'input_boolean.image_processing_enabled',
    })

    motion_lighting = create_motion_lighting_app()

    return motion_lighting


def create_motion_lighting_app():
    motion_lighting = MotionLighting(None, None, None, None, None, None, None,
                                     None)
    motion_lighting.initialize()
    motion_lighting.name = 'motion_lighting'

    def info_timer(self, handle):
        if handle is None:
            return None

        return datetime.now() + timedelta(minutes=15), 0, {}

    motion_lighting.info_timer = MethodType(info_timer, motion_lighting)

    return motion_lighting


def test_should_not_turn_on_light_when_enabler_is_off(given_that,
                                                      motion_lighting,
                                                      assert_that):
    expect_states(given_that, motion_enabled='off', lighting_mode='Dark',
                  light='off', motion='on')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='on')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_on(brightness=200,
                                                        transition=2)
    assert_that('switch.tv').was_not.turned_on()


def test_should_not_turn_on_light_when_motion_triggered_and_is_not_dark(
        given_that,
        motion_lighting,
        assert_that):
    expect_states(given_that, motion_enabled='on', lighting_mode='Not Dark',
                  light='off', motion='on')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='on')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_on(brightness=200,
                                                        transition=2)
    assert_that('switch.tv').was_not.turned_on()


def test_should_turn_on_light_when_motion_triggered_and_light_is_on_already(
        given_that,
        motion_lighting,
        assert_that):
    given_that.state_of('input_boolean.is_motion_enabled').is_set_to('on')
    given_that.state_of('input_select.lighting_mode').is_set_to('Dark')
    given_that.state_of('light.office_light').is_set_to('on',
                                                        {'brightness': 100})
    given_that.state_of('switch.tv').is_set_to('on')
    given_that.state_of('binary_sensor.motion').is_set_to('on')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='on')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was.turned_on(brightness=200,
                                                    transition=2)
    assert_that('switch.tv').was_not.turned_on()


def test_should_turn_on_light_when_motion_triggered_and_is_dark(given_that,
                                                                motion_lighting,
                                                                assert_that):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='off', motion='on')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='on')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was.turned_on(brightness=200,
                                                    transition=2)
    assert_that('switch.tv').was.turned_on()


def test_should_not_turn_on_light_when_triggered_by_time(given_that,
                                                         motion_lighting,
                                                         assert_that):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='off', motion='on')

    trigger_info = create_time_trigger_info()
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_on(brightness=200,
                                                        transition=2)
    assert_that('switch.tv').was_not.turned_on()


def test_should_turn_off_light_when_all_motion_stopped(given_that,
                                                       motion_lighting,
                                                       assert_that,
                                                       time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='off')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(25).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(35).seconds()
    assert_that('light.office_light').was.turned_off(transition=2)
    assert_that('switch.tv').was.turned_off()


def test_should_not_turn_off_lights_when_motion_stopped_and_light_is_manually_turned_off(
        given_that,
        motion_lighting,
        assert_that,
        time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='off')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(20).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    given_that.state_of('light.office_light').is_set_to('off')
    trigger_info = create_state_trigger_info('light.office_light', to='off')
    motion_lighting.trigger_handler(trigger_info)

    time_travel.fast_forward(35).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()


def test_should_not_turn_off_lights_when_motion_stopped_and_light_is_manually_turned_off_and_on_again(
        given_that,
        motion_lighting,
        assert_that,
        time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='off')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(20).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    given_that.state_of('light.office_light').is_set_to('off')
    trigger_info = create_state_trigger_info('light.office_light', to='off')
    motion_lighting.trigger_handler(trigger_info)

    given_that.state_of('light.office_light').is_set_to('on')
    trigger_info = create_state_trigger_info('light.office_light', to='on')
    motion_lighting.trigger_handler(trigger_info)

    time_travel.fast_forward(65).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()


def test_should_turn_off_light_when_only_one_motion_stopped(given_that,
                                                            motion_lighting,
                                                            assert_that,
                                                            time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='off', motion2='on')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(25).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(35).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()


def test_should_dim_and_turn_off_light_when_motion_stopped(given_that,
                                                           motion_lighting,
                                                           assert_that,
                                                           time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='off')

    given_that.state_of('light.office_light').is_set_to('on', {
        'state': 'on',
        'attributes': {
            'brightness': 200
        }
    })

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(25).seconds()
    assert_that('light.office_light').was.turned_on(transition=2,
                                                    brightness=80)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(35).seconds()
    assert_that('light.office_light').was.turned_off(transition=2)
    assert_that('switch.tv').was.turned_off()


def test_should_not_turn_off_light_when_motion_stopped_and_resumed(
        given_that,
        motion_lighting,
        assert_that,
        time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='off')

    given_that.state_of('light.office_light').is_set_to('on', {
        'state': 'on',
        'attributes': {
            'brightness': 200
        }
    })

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(25).seconds()
    assert_that('light.office_light').was.turned_on(transition=2,
                                                    brightness=80)
    assert_that('switch.tv').was_not.turned_off()

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='on')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was.turned_on(brightness=200,
                                                    transition=2)
    assert_that('switch.tv').was_not.turned_on()


def test_should_not_turn_off_light_when_triggered_by_time(given_that,
                                                          motion_lighting,
                                                          assert_that,
                                                          time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='off')

    trigger_info = create_time_trigger_info()
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(25).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(35).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()


def test_should_turn_off_light_when_motion_state_is_unavailable(given_that,
                                                                motion_lighting,
                                                                assert_that,
                                                                time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='unavailable')

    trigger_info = create_state_trigger_info('binary_sensor.motion',
                                             to='unavailable')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(25).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(35).seconds()
    assert_that('light.office_light').was.turned_off(transition=2)
    assert_that('switch.tv').was.turned_off()


def test_should_turn_off_light_when_lighting_mode_is_not_dark(
        given_that,
        motion_lighting,
        assert_that,
        time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Not Dark',
                  light='on', motion='off')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(25).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(35).seconds()
    assert_that('light.office_light').was.turned_off(transition=2)
    assert_that('switch.tv').was.turned_off()


def test_should_not_turn_off_light_when_enabler_is_off(
        given_that,
        motion_lighting,
        assert_that,
        time_travel):
    expect_states(given_that, motion_enabled='off', lighting_mode='Dark',
                  light='on', motion='off')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(25).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()

    time_travel.fast_forward(35).seconds()
    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()


def test_should_not_turn_on_light_when_not_in_turn_on_time(
        given_that,
        motion_lighting_with_turn_on_time,
        assert_that,
        hass_functions):
    now_is_between(hass_functions, '21:00:00', '16:00:00')

    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='off', motion='off')

    trigger_info = create_time_trigger_info()
    motion_lighting_with_turn_on_time.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_on(brightness=200,
                                                        transition=2)
    assert_that('switch.tv').was_not.turned_on()
    assert_that('input_boolean.is_motion_enabled').was_not.turned_off()


def test_should_turn_on_light_when_in_turn_on_time(
        given_that,
        motion_lighting_with_turn_on_time,
        assert_that,
        hass_functions):
    now_is_between(hass_functions, '16:00:00', '21:00:00')

    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='off', motion='off')

    trigger_info = create_time_trigger_info()
    motion_lighting_with_turn_on_time.trigger_handler(trigger_info)

    assert_that('light.office_light').was.turned_on(brightness=200,
                                                    transition=2)
    assert_that('switch.tv').was.turned_on()
    assert_that('input_boolean.is_motion_enabled').was.turned_off()


def test_should_not_turn_on_light_when_in_turn_on_time_and_light_is_on_already(
        given_that,
        motion_lighting_with_turn_on_time,
        assert_that,
        hass_functions):
    now_is_between(hass_functions, '16:00:00', '21:00:00')

    given_that.state_of('input_boolean.is_motion_enabled').is_set_to('off')
    given_that.state_of('input_select.lighting_mode').is_set_to('Dark')
    given_that.state_of('light.office_light').is_set_to('on',
                                                        {'brightness': 200})
    given_that.state_of('switch.tv').is_set_to('on')
    given_that.state_of('binary_sensor.motion').is_set_to('off')

    trigger_info = create_time_trigger_info()
    motion_lighting_with_turn_on_time.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_on(brightness=200,
                                                        transition=2)
    assert_that('switch.tv').was_not.turned_on()
    assert_that('input_boolean.is_motion_enabled').was_not.turned_off()


def test_should_turn_off_light_when_not_in_turn_on_time(
        given_that,
        motion_lighting_with_turn_on_time,
        assert_that,
        hass_functions):
    now_is_between(hass_functions, '21:00:00', '16:00:00')

    expect_states(given_that, motion_enabled='off', lighting_mode='Dark',
                  light='on', motion='off')

    trigger_info = create_time_trigger_info()
    motion_lighting_with_turn_on_time.trigger_handler(trigger_info)

    assert_that('light.office_light').was.turned_off(transition=2)
    assert_that('switch.tv').was.turned_off()
    assert_that('input_boolean.is_motion_enabled').was.turned_on()


def test_should_not_turn_off_light_when_not_in_turn_on_time_and_light_is_off_already(
        given_that,
        motion_lighting_with_turn_on_time,
        assert_that,
        hass_functions):
    now_is_between(hass_functions, '21:00:00', '16:00:00')

    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='off', motion='off')

    trigger_info = create_time_trigger_info()
    motion_lighting_with_turn_on_time.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()
    assert_that('input_boolean.is_motion_enabled').was_not.turned_on()


def test_should_not_turn_off_light_when_not_in_turn_on_time_and_light_is_on_by_motion(
        given_that,
        motion_lighting_with_turn_on_time,
        assert_that,
        hass_functions):
    now_is_between(hass_functions, '21:00:00', '16:00:00')

    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='on', motion='on')

    trigger_info = create_time_trigger_info()
    motion_lighting_with_turn_on_time.trigger_handler(trigger_info)

    assert_that('light.office_light').was_not.turned_off(transition=2)
    assert_that('switch.tv').was_not.turned_off()
    assert_that('input_boolean.is_motion_enabled').was_not.turned_on()


def test_should_turn_on_light_when_person_is_detected(
        given_that,
        motion_lighting_with_image_processing,
        assert_that):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='off', motion='on')

    given_that.state_of('input_boolean.image_processing_enabled').is_set_to(
        'off')

    trigger_info = create_state_trigger_info('image_processing.entity_id',
                                             to='on')
    motion_lighting_with_image_processing.trigger_handler(trigger_info)

    assert_that('light.office_light').was.turned_on(brightness=200,
                                                    transition=2)
    assert_that('switch.tv').was.turned_on()


def test_should_start_image_processing_when_motion_stopped(
        given_that,
        motion_lighting_with_image_processing,
        assert_that,
        time_travel):
    expect_states(given_that, motion_enabled='on', lighting_mode='Dark',
                  light='off', motion='off')

    given_that.state_of('input_boolean.image_processing_enabled').is_set_to(
        'off')
    given_that.state_of('image_processing.entity_id').is_set_to('off')

    trigger_info = create_state_trigger_info('binary_sensor.motion', to='off')
    motion_lighting_with_image_processing.trigger_handler(trigger_info)

    assert_that('input_boolean.image_processing_enabled').was.turned_on()

    given_that.state_of('input_boolean.image_processing_enabled').is_set_to(
        'on')

    time_travel.fast_forward(25).seconds()
    assert_that('input_boolean.image_processing_enabled').was_not.turned_off()

    time_travel.fast_forward(35).seconds()
    assert_that('input_boolean.image_processing_enabled').was.turned_off()


def expect_states(given_that, motion_enabled, lighting_mode, light, motion,
                  motion2=None):
    given_that.state_of('input_boolean.is_motion_enabled').is_set_to(
        motion_enabled)
    given_that.state_of('input_select.lighting_mode').is_set_to(lighting_mode)
    given_that.state_of('light.office_light').is_set_to(light)
    given_that.state_of('switch.tv').is_set_to(light)
    given_that.state_of('binary_sensor.motion').is_set_to(motion)

    if motion2 is None:
        motion2 = motion

    given_that.state_of('binary_sensor.motion_2').is_set_to(motion2)
