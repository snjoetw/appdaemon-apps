import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback
from notifier import Notifier, Message, NotifierType


class LightSetting:
    def __init__(self, config):
        if isinstance(config, dict):
            self._light_entity_id = config['light_entity_id']
            self._delegate_light_entity_id = config.get(
                'delegate_light_entity_id', self._light_entity_id)
        else:
            self._light_entity_id = config
            self._delegate_light_entity_id = config

    @property
    def light_entity_id(self):
        return self._light_entity_id

    @property
    def delegate_light_entity_id(self):
        return self._delegate_light_entity_id


class MonitorSetting:
    def __init__(self, config):
        self._noise_entity_id = config['noise_entity_id']
        self._light_data = config['light_data']

    @property
    def noise_entity_id(self):
        return self._noise_entity_id

    @property
    def light_data(self):
        return self._light_data


class NoiseLevelMonitor(BaseAutomation):
    light_settings: list
    monitor_settings: list
    is_monitoring: bool
    sleeping_time_entity_id: str

    def initialize(self):
        self.sleeping_time_entity_id = self.cfg.value('sleeping_time_entity_id')
        self.is_monitoring = False

        monitor_configs = self.cfg.list('monitor_settings', [])
        self.monitor_settings = []
        for config in monitor_configs:
            self.monitor_settings.append(MonitorSetting(config))

        light_configs = self.cfg.list('light_settings', [])
        self.light_settings = []
        for config in light_configs:
            self.light_settings.append(LightSetting(config))

        for setting in self.monitor_settings:
            self.listen_state(self.noise_state_change_handler, setting.noise_entity_id)

        for setting in self.light_settings:
            self.listen_state(self.light_state_change_handler, setting.light_entity_id)

            if setting.light_entity_id != setting.delegate_light_entity_id:
                self.listen_state(self.light_state_change_handler, setting.delegate_light_entity_id)

    @monitored_callback
    def noise_state_change_handler(self, entity, attribute, old, new, kwargs):
        if new != 'on':
            return

        if not self.is_monitoring:
            self.debug('Skipping ... not monitoring')
            return

        notifier: Notifier = self.get_app('notifier')
        notifier.notify(Message([NotifierType.IOS], ['joe'], None, 'Noise detected: {}'.format(entity)))

        self.debug('Noise detected: {}'.format(entity))
        light_data = self.figure_light_data(entity)
        self.debug('Using light_data={}'.format(light_data))

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(handle_noise_detected, self, setting, light_data): setting for setting in
                       self.light_settings}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.error('Error when running actions: {}\n{}'.format(e, traceback.format_exc()))

    @monitored_callback
    def light_state_change_handler(self, entity, attribute, old, new, kwargs):
        if self.should_monitor():
            self.start_monitor()
        else:
            self.stop_monitor()

    def figure_light_data(self, triggered_entity_id):
        for setting in self.monitor_settings:
            if triggered_entity_id == setting.noise_entity_id:
                return setting.light_data

        return None

    def should_turn_on_light(self, light_setting):
        if self.get_state(light_setting.light_entity_id) == 'on':
            return True

        if self.get_state(light_setting.delegate_light_entity_id) == 'on':
            return True

        return False

    def should_monitor(self):
        is_sleeping_time = self.get_state(self.sleeping_time_entity_id)
        if is_sleeping_time != 'on':
            return False

        for setting in self.light_settings:
            if self.get_state(setting.light_entity_id) == 'on':
                return True
            if self.get_state(setting.delegate_light_entity_id) == 'on':
                return True

        return False

    def start_monitor(self):
        just_started = False

        for setting in self.monitor_settings:
            if self.get_state(setting.noise_entity_id) == 'unavailable':
                self.call_service('ffmpeg/restart', entity_id=setting.noise_entity_id)
                self.sleep(10)
                self.call_service('ffmpeg/start', entity_id=setting.noise_entity_id)

                just_started = True

        if just_started and not self.is_monitoring:
            self.enable_monitor(True)

    def stop_monitor(self):
        for setting in self.monitor_settings:
            if self.get_state(setting.noise_entity_id) != 'unavailable':
                self.enable_monitor(False)

                self.call_service('ffmpeg/restart', entity_id=setting.noise_entity_id)
                self.sleep(10)
                self.call_service('ffmpeg/stop', entity_id=setting.noise_entity_id)
                self.set_state(setting.noise_entity_id, state='off')

    def enable_monitor(self, enable):
        self.is_monitoring = enable

        if enable:
            self.debug('Enabled monitoring ...')
        else:
            self.debug('Disabled monitoring ...')


def handle_noise_detected(app, light_setting, light_data):
    if not app.should_turn_on_light(light_setting):
        return

    original = app.get_state(
        light_setting.delegate_light_entity_id,
        attribute='all')

    if original['state'] == 'off':
        app.turn_on(light_setting.delegate_light_entity_id, **{
            'brightness': 255,
        })

    app.turn_on(light_setting.delegate_light_entity_id, **{
        **light_data,
        'flash': 'long',
    })

    app.sleep(3)

    if original['state'] == 'on':
        app.turn_on(light_setting.delegate_light_entity_id, **{
            'rgb_color': original['attributes']['rgb_color'],
            'brightness': original['attributes']['brightness'],
        })
    else:
        app.turn_off(light_setting.delegate_light_entity_id)
