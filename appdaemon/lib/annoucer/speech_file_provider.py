import requests

from lib.annoucer.announcer_config import AnnouncerConfig
from lib.core.app_accessible import AppAccessible


class SpeechFileProvider(AppAccessible):
    def __init__(self, app, announcer_config: AnnouncerConfig):
        super().__init__(app)

        self._api_url = '{}/api/tts_get_url'.format(announcer_config.api_base_url)
        self._api_token = announcer_config.api_token
        self._tts_base_filepath = announcer_config.tts_base_filepath
        self._platform = announcer_config.tts_platform

    def provide(self, message):
        self.debug('About to get tts filename: {}'.format(message))
        response = requests.post(self._api_url,
                                 json={
                                     'platform': self._platform,
                                     'message': message,
                                     'cache': True,
                                 },
                                 headers={
                                     'Authorization': self._api_token,
                                     'Content-Type': 'application/json'
                                 })

        self.debug('Received get_tts response: {}'.format(response))

        response.raise_for_status()
        tts_url = response.json().get('url')
        tts_filename = tts_url.rsplit('/', 1)[-1]
        filepath = self._tts_base_filepath + tts_filename
        return SpeechFile(filepath)


class AmazonPollySpeechFileProvider(SpeechFileProvider):
    def __init__(self, app, announcer_config: AnnouncerConfig):
        super().__init__(app, announcer_config)
        self._default_speak_speed = announcer_config.default_speak_speed

    def provide(self, message):
        if not message.startswith('<speak>'):
            if self._default_speak_speed is not None and '<prosody rate' not in message:
                message = '<prosody rate="%s">'.format(self._default_speak_speed) + message + '</prosody>'
            message = '<speak>' + message + '</speak>'

        return super().provide(message)


class SpeechFile:
    def __init__(self, tts_filepath):
        self._filepath = tts_filepath
        self._filename = tts_filepath.rsplit('/', 1)[-1]

    @property
    def filepath(self):
        return self._filepath

    @property
    def filename(self):
        return self._filename
