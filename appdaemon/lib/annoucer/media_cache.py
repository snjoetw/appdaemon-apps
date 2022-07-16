import os
import re
from enum import Enum

from lib.annoucer.announcer_config import AnnouncerConfig
from lib.annoucer.media_data import MediaData
from lib.core.app_accessible import AppAccessible

CACHE_FILE_MATCHER = re.compile(r'cached_(.+?)\.mp3')
CACHE_FILE_PATTERN = 'cached_{}@{}.mp3'


class CacheType(Enum):
    PERMANENT = 1
    TEMPORARY = 2


class MediaCache(AppAccessible):
    def __init__(self, app, announcer_config: AnnouncerConfig):
        super().__init__(app)

        self._api_base_url = announcer_config.api_base_url
        self._cache_speech_filepath = announcer_config.library_base_filepath + 'tts/'
        self._temp_speech_filepath = announcer_config.library_base_filepath + 'tts/tmp/'
        self._library_base_url_path = announcer_config.library_base_url_path

        self._cache = {}

        self._init_file_cache()
        self._cleanup_temp_cache()

    def _cleanup_temp_cache(self):
        deleted_count = 0

        for filename in os.listdir(self._temp_speech_filepath):
            file_path = os.path.join(self._temp_speech_filepath, filename)
            try:
                os.unlink(file_path)
                deleted_count += 1
            except Exception as e:
                self.error('Failed to delete {}. Reason: {}'.format(file_path, e))

        self.log('Deleted {} temp file in {}'.format(deleted_count, self._temp_speech_filepath))

    def _init_file_cache(self):
        self.debug('About to load file cache from {}'.format(self._cache_speech_filepath))

        loaded_count = 0
        for filename in os.listdir(self._cache_speech_filepath):
            matched = CACHE_FILE_MATCHER.match(filename)
            if matched:
                cache_key, *data = matched.group(1).split('@')
                duration = 0 if not len(data) else int(data[0])

                media = self._create_media_data(CacheType.PERMANENT, filename, duration)
                self.put(cache_key.lower(), media)
                loaded_count += 1

        self.debug('Loaded {} files'.format(loaded_count))

    def _create_media_data(self, cache_type: CacheType, filepath, duration):
        filename = filepath.rsplit('/', 1)[-1]
        if cache_type == CacheType.TEMPORARY:
            url = self._api_base_url + self._library_base_url_path + 'tts/tmp/{}'.format(filename)
        else:
            url = self._api_base_url + self._library_base_url_path + 'tts/{}'.format(filename)
        return MediaData(url, duration)

    def create(self, cache_type: CacheType, audio, cache_key=None, filename=None):
        duration = round(audio.duration_seconds)

        if cache_type == CacheType.TEMPORARY:
            filepath = self._temp_speech_filepath + filename
            audio.export(filepath, format='mp3')
            return self._create_media_data(cache_type, filepath, duration)

        filename = CACHE_FILE_PATTERN.format(cache_key, duration)
        filepath = self._cache_speech_filepath + filename
        audio.export(filepath, format='mp3')
        media = self._create_media_data(cache_type, filepath, duration)
        self.put(cache_key, media)
        return media

    def put(self, cache_key, media):
        self._cache[cache_key.lower()] = media

    def get(self, cache_key):
        cache_key = cache_key.lower()
        if cache_key in self._cache:
            return self._cache[cache_key.lower()]

        return None
