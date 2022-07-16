class Announcement:
    def __init__(self, message, use_cache, prelude_name, is_critical, players):
        self._message = message
        self._use_cache = use_cache
        self._prelude_name = prelude_name
        self._is_critical = is_critical
        self._players = players

    @property
    def message(self):
        return self._message

    @property
    def use_cache(self):
        return self._use_cache

    @property
    def prelude_name(self):
        return self._prelude_name

    @property
    def is_critical(self):
        return self._is_critical

    @property
    def players(self):
        return self._players

    def __repr__(self):
        return "{}(message={}, use_cache={}, prelude_name={}, is_critical={})".format(
            self.__class__.__name__,
            self.message,
            self.use_cache,
            self.prelude_name,
            self.is_critical)

    def __eq__(self, other):
        if not isinstance(other, Announcement):
            return NotImplemented

        return self.message == other.message \
               and self.use_cache == other.use_cache \
               and self.prelude_name == other.prelude_name \
               and self.is_critical == other.is_critical

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.message, self.use_cache, self.prelude_name, self.is_critical))
