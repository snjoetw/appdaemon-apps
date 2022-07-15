from typing import Dict


class AnnouncerConfig:
    _default_volume: Dict
    _enabler_entity_id: str
    _api_token: str
    _api_base_url: str
    _sleeping_time_entity_id: str

    def __init__(self, config):
        self._tts_platform = config['tts_platform']
        self._sleeping_time_entity_id = config['sleeping_time_entity_id']
        self._api_base_url = config['api_base_url']
        self._api_token = config['api_token']
        self._enabler_entity_id = config['enabler_entity_id']
        self._default_volume = config['default_volume']
        self._library_base_filepath = config['library_base_filepath']
        self._library_base_url_path = config['library_base_url_path']
        self._tts_base_filepath = config['tts_base_filepath']
        self._sound_path = config['sound_path']
        self._default_speak_speed = config.get('default_speak_speed')

    @property
    def sleeping_time_entity_id(self):
        return self._sleeping_time_entity_id

    @property
    def tts_platform(self):
        return self._tts_platform

    @property
    def api_base_url(self):
        return self._api_base_url

    @property
    def api_token(self):
        return self._api_token

    @property
    def enabler_entity_id(self):
        return self._enabler_entity_id

    @property
    def default_volume(self):
        return self._default_volume

    @property
    def library_base_filepath(self):
        return self._library_base_filepath

    @property
    def library_base_url_path(self):
        return self._library_base_url_path

    @property
    def tts_base_filepath(self):
        return self._tts_base_filepath

    @property
    def sound_path(self):
        return self._sound_path

    @property
    def default_speak_speed(self):
        return self._default_speak_speed
