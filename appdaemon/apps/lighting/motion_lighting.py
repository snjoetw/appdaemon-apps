from typing import List, Any

from base_automation import BaseAutomation

from lib.actions import TurnOnAction, get_action, TurnOffAction
from lib.actions import figure_light_settings
from lib.constraints import get_constraint, Constraint
from lib.core.monitored_callback import monitored_callback
from lib.triggers import TriggerInfo

DEFAULT_SCENE = 'Default'
TURN_ON_TRIGGER_STATES = ['on', 'unlocked', 'open', 'opening']
PATHWAY_LIGHT_TRIGGER_ENTITY_ID = "pathway_light_trigger_entity_id"


class Scene:
    _scene_name: str
    _turn_off_delay: int
    _light_settings: List[Any]
    _constraints: List[Constraint]

    def __init__(self, scene_name: str, turn_off_delay: int, light_settings: List[Any], constraints: List[Constraint]):
        self._scene_name = scene_name
        self._turn_off_delay = turn_off_delay
        self._light_settings = light_settings
        self._constraints = constraints

    @property
    def scene_name(self):
        return self._scene_name

    @property
    def turn_off_delay(self):
        return self._turn_off_delay

    @property
    def light_settings(self):
        return self._light_settings

    @property
    def constraints(self):
        return self._constraints or []

    def check_constraints(self, trigger_info):
        for constraint in self.constraints:
            if not constraint.check(trigger_info):
                return False
        return True

    def __repr__(self):
        return "{}(scene_name={}, turn_off_delay={}, scene_name={}, scene_name={})".format(
            self.__class__.__name__,
            self.scene_name,
            self.turn_off_delay,
            self.light_settings,
            self.constraints)


def create_turn_off_action(app, entity_id):
    return get_action(app, {
        'platform': 'delay',
        'actions': [{
            'platform': 'turn_off',
            'entity_id': entity_id
        }],
    })


class MotionLighting(BaseAutomation):
    motion_entity_ids: List[str]
    darkness_entity_id: str
    enabler_entity_id: str
    scene_entity_id: str
    turn_off_delay: int
    dim_light_before_turn_off: bool
    turn_on_constraints: List[Constraint]
    turn_off_light_entity_ids: List[str]
    pathway_light_turn_off_delay: int
    scenes: List[Scene]

    def initialize(self):
        self.motion_entity_ids = self.cfg.list('motion_entity_id')
        self.darkness_entity_id = self.cfg.value('darkness_entity_id')
        self.enabler_entity_id = self.cfg.value('enabler_entity_id')
        self.scene_entity_id = self.cfg.value('scene_entity_id')
        self.turn_off_delay = self.cfg.value('turn_off_delay')
        self.dim_light_before_turn_off = self.cfg.value('dim_light_before_turn_off', True)
        self.turned_on_by = None
        self.scenes = self._create_scenes()

        # pathway light
        self.pathway_light_turn_off_delay = self.cfg.int('pathway_light_turn_off_delay', 20)

        self.turn_on_constraints = []
        for constraint in self.cfg.list('turn_on_constraints', []):
            self.turn_on_constraints.append(get_constraint(self, constraint))

        light_entity_ids = self._figure_participated_light_entity_ids()
        self.turn_off_light_entity_ids = self.cfg.list('turn_off_light_entity_ids', light_entity_ids)
        self.turn_off_lights_handle = None

        if self.is_enabled:
            self._register_motion_state_change_event()

        if self.enabler_entity_id:
            self.listen_state(self._enabler_state_change_handler, self.enabler_entity_id)

    def _figure_participated_light_entity_ids(self):
        entity_ids = set()
        for scene in self.scenes:
            for entity_id in figure_light_settings(scene.light_settings).keys():
                entity_ids.add(entity_id)

        return list(entity_ids)

    @property
    def is_enabled(self):
        return self.enabler_entity_id is None or self.get_state(self.enabler_entity_id) == 'on'

    def _register_motion_state_change_event(self):
        if not self.motion_entity_ids:
            self.motion_event_handlers = []
            return

        self.motion_event_handlers = [self.listen_state(self._motion_state_change_handler, motion_entity_id)
                                      for motion_entity_id in self.motion_entity_ids]
        self.debug('Registered motion state handler, entity_ids={}'.format(self.motion_entity_ids))

    @monitored_callback
    def _enabler_state_change_handler(self, entity, attribute, old, new, kwargs):
        if new == 'on':
            self._register_motion_state_change_event()
            return

        [self.cancel_listen_state(handle) for handle in self.motion_event_handlers]
        self.debug('Cancelled motion state handler, entity_ids={}'.format(self.motion_entity_ids))

    @monitored_callback
    def _motion_state_change_handler(self, entity, attribute, old, new, kwargs):
        self._cancel_turn_off_delay()

        self.debug('Motion triggered by entity_id={}, new={}, old={}'.format(entity, new, old))

        trigger_info = TriggerInfo("state", {
            "entity_id": entity,
            "attribute": attribute,
            "from": old,
            "to": new,
        })

        if self._should_turn_on_lights(trigger_info):
            self._turn_on_lights(trigger_info)
        elif self._should_turn_off_lights(trigger_info):
            self._turn_off_lights(trigger_info)

    def _should_turn_on_lights(self, trigger_info):
        if not self.is_enabled:
            return False

        if self.darkness_entity_id and self.get_state(self.darkness_entity_id) == 'Not Dark':
            return False

        motion_state = trigger_info.data.get('to')
        if motion_state not in TURN_ON_TRIGGER_STATES:
            return False

        for constraint in self.turn_on_constraints:
            if not constraint.check(trigger_info):
                return False

        return True

    def _should_turn_off_lights(self, trigger_info):
        motion_state = trigger_info.data.get('to')

        if len(self.motion_entity_ids) == 1:
            return motion_state not in TURN_ON_TRIGGER_STATES

        for motion_entity_id in self.motion_entity_ids:
            if self.get_state(motion_entity_id) in TURN_ON_TRIGGER_STATES:
                return False

        return True

    def _turn_on_lights(self, trigger_info=None):
        scene = self._figure_scene(trigger_info)
        self.debug('Using scene={}'.format(scene))

        if scene is None:
            return
        if scene.light_settings is None or not scene.light_settings:
            return

        if trigger_info:
            self.turned_on_by = trigger_info.platform

        actions = [TurnOnAction(self, {'entity_ids': [light_setting]}) for light_setting in scene.light_settings]
        self.do_actions(actions)

    def _figure_scene(self, trigger_info=None):
        scene_name = DEFAULT_SCENE if self.scene_entity_id is None else self.get_state(self.scene_entity_id)
        return self._get_scene(scene_name, trigger_info) or self._get_scene(DEFAULT_SCENE, trigger_info)

    def _get_scene(self, scene_name, trigger_info=None):
        for scene in self.scenes:
            if scene_name != scene.scene_name:
                continue

            if not scene.check_constraints(trigger_info):
                self.debug('Scene constraint does not match')
                continue

            self.debug('All scene constraints passed')
            return scene
        return None

    def _turn_off_lights(self, trigger_info=None):
        turn_off_delay = self._figure_turn_off_delay(trigger_info)

        if turn_off_delay is None:
            return

        self.turned_on_by = None

        self.debug('About to turn lights off in {} second'.format(turn_off_delay))
        self.turn_off_lights_handle = self.run_in(self._turn_off_lights_handler, turn_off_delay)

    def _cancel_turn_off_delay(self):
        if self.turn_off_lights_handle is not None:
            self.cancel_timer(self.turn_off_lights_handle)
            self.turn_off_lights_handle = None
            self.debug('Cancelled turn off delay timer')

    def _turn_off_lights_handler(self, kwargs={}):
        actions = [TurnOffAction(self, {
            'entity_ids': self.turn_off_light_entity_ids,
            'dim_light_before_turn_off': self.dim_light_before_turn_off,
        })]
        self.do_actions(actions)
        self.turn_off_lights_handle = None

    def _figure_turn_off_delay(self, trigger_info: TriggerInfo):
        if trigger_info is not None and trigger_info.data.get('entity_id') == PATHWAY_LIGHT_TRIGGER_ENTITY_ID:
            return self.pathway_light_turn_off_delay

        if trigger_info is not None and trigger_info.platform == 'time':
            return 0

        scene = self._figure_scene(trigger_info)
        if scene:
            return scene.turn_off_delay

        return self.turn_off_delay

    def trigger_pathway_light(self):
        self._motion_state_change_handler(PATHWAY_LIGHT_TRIGGER_ENTITY_ID, None, 'off', 'on', None)
        # trigger turn off immediately so that we can start pathway light turn off counter
        self._motion_state_change_handler(PATHWAY_LIGHT_TRIGGER_ENTITY_ID, None, 'on', 'off', None)

    def _create_scenes(self) -> List[Scene]:
        scene_configs = self.cfg.value('scenes', [])
        default_turn_off_delay = self.cfg.value('turn_off_delay')
        scenes = []

        for config in scene_configs:
            constraints = [get_constraint(self, c) for c in config.get('constraints', [])]
            scenes.append(Scene(
                config['scene_name'],
                config.get('turn_off_delay', default_turn_off_delay),
                config.get('lights', []),
                constraints))
        return scenes
