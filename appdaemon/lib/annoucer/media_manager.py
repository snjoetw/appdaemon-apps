import hashlib
import re

from pydub import AudioSegment

from lib.annoucer.announcement import Announcement
from lib.annoucer.announcer_config import AnnouncerConfig
from lib.annoucer.media_cache import MediaCache, CacheType
from lib.annoucer.media_data import MediaData
from lib.annoucer.speech_file_provider import AmazonPollySpeechFileProvider, SpeechFileProvider
from lib.core.app_accessible import AppAccessible

CACHE_KEY_PATTERN = '{0}_{1}'
CACHE_KEY_PATTERN_WITH_CHIME = '{0}_{1}_chime'
CHIME_FILE_SUFFIX = '_chime'


def to_cache_key(announcement: Announcement, with_chime):
    message = announcement.message
    prelude_name = announcement.prelude_name

    msg_hash = hashlib.sha1(bytes(message, 'utf-8')).hexdigest()
    message = re.sub(r'[^a-zA-Z0-9 ]+', '', message).replace(' ', '_')

    if prelude_name:
        message += '_' + prelude_name

    if with_chime:
        return CACHE_KEY_PATTERN_WITH_CHIME.format(msg_hash, message).lower()

    return CACHE_KEY_PATTERN.format(msg_hash, message).lower()


class MediaManager(AppAccessible):
    _cache: MediaCache
    _speech_file_provider: SpeechFileProvider
    _config: AnnouncerConfig

    def __init__(self, app, announcer_config: AnnouncerConfig):
        super().__init__(app)

        self._config = announcer_config
        self._speech_file_provider = self._figure_speech_file_provider()
        self._cache = MediaCache(app, announcer_config)

    @property
    def config(self):
        return self._config

    def _figure_speech_file_provider(self):
        if self.config.tts_platform == 'amazon_polly':
            return AmazonPollySpeechFileProvider(self, self.config)

        return SpeechFileProvider(self, self.config)

    def get_media(self, announcement: Announcement, with_chime):
        if announcement.prelude_name:
            with_chime = False

        cache_key = to_cache_key(announcement, with_chime)
        cached = self._cache.get(cache_key)

        if announcement.use_cache and cached:
            self.debug('Found cached media file for announcement={}'.format(announcement))
            return cached

        speech_file = self._speech_file_provider.provide(announcement.message)
        prelude_filepath = self._figure_sound_filepath(announcement.prelude_name)

        if announcement.use_cache:
            return self._create_cached_audio_file(cache_key, speech_file, with_chime, prelude_filepath)

        return self._create_temp_audio_file(speech_file, with_chime, prelude_filepath)

    def get_sound_media(self, sound_name, duration=0):
        url = self.config.api_base_url + self.config.library_base_url_path + self.config.sound_path[sound_name]
        return MediaData(url, duration)

    def _figure_sound_filepath(self, sound_name):
        if sound_name in self.config.sound_path:
            return self.config.library_base_filepath + self.config.sound_path[sound_name]

        return None

    def _create_cached_audio_file(self, audio_key, speech_file, with_chime, prelude_filepath):
        # create "not with_chime" version first
        cache_key = audio_key
        if cache_key.endswith(CHIME_FILE_SUFFIX):
            cache_key = cache_key.replace(CHIME_FILE_SUFFIX, '')
        else:
            cache_key = cache_key + CHIME_FILE_SUFFIX
        self._create_and_cache_audio_file(cache_key, speech_file, not with_chime, prelude_filepath)

        # then again create "with_chime" version
        cache_key = audio_key
        self._create_and_cache_audio_file(cache_key, speech_file, with_chime, prelude_filepath)

        return self._cache.get(cache_key)

    def _create_and_cache_audio_file(self, cache_key, speech_file, with_chime, prelude_filepath):
        audio = self._create_audio(speech_file, with_chime, prelude_filepath)
        self._cache.create(CacheType.PERMANENT, audio, cache_key=cache_key)

    def _create_temp_audio_file(self, speech_file, with_chime, prelude_filepath):
        audio = self._create_audio(speech_file, with_chime, prelude_filepath)
        return self._cache.create(CacheType.TEMPORARY, audio, filename=speech_file.filename)

    def _create_audio(self, speech_file, with_chime, prelude_filepath=None):
        combined = AudioSegment.empty()

        if with_chime:
            chime = AudioSegment.from_mp3(self._figure_sound_filepath('chime'))
            combined += chime

        if prelude_filepath:
            prelude = AudioSegment.from_mp3(prelude_filepath)
            combined += prelude

        if speech_file:
            combined += self._retrieve_speech_file(speech_file.filepath)

        return combined

    def _retrieve_speech_file(self, speech_filepath):
        error = None
        for i in range(0, 3):
            try:
                return AudioSegment.from_mp3(speech_filepath)
            except FileNotFoundError as ex:
                self.warn('Unable to retrieve speech file, retrying ...: {}'.format(speech_filepath))
                error = ex

            self.app.sleep(1)

        if error is not None:
            raise error

        self.error('Unable to retrieve speech file: {}'.format(speech_filepath))
