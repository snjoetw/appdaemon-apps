class MediaData:
    def __init__(self, url, duration):
        self._media_url = url
        self._duration = int(duration)

    @property
    def media_url(self):
        return self._media_url

    @property
    def duration(self):
        return self._duration

    def __repr__(self):
        return "{}(media_url={}, duration={})".format(self.__class__.__name__, self.media_url, self.duration)
