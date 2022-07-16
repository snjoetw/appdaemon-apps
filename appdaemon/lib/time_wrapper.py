class DateTimeWrapper:
    def __init__(self, app, dt):
        self._app = app

        if isinstance(dt, str):
            self._dt = self._parse_datetime(dt)
        else:
            self._dt = dt

    def diff(self, another_dt):
        return self._dt.replace(tzinfo=None) - another_dt.replace(tzinfo=None)

    def datetime(self):
        return self._dt

    def before(self, dt_str):
        time = self._parse_datetime(dt_str)
        return self.datetime() < time

    def after(self, dt_str):
        time = self._parse_datetime(dt_str)
        return time < self.datetime()

    def between(self, start_str, end_str):
        return self.after(start_str) and self.before(end_str)

    def _parse_datetime(self, dt_str):
        return self._app.parse_datetime(dt_str).astimezone(self._app.AD.tz)


class NowWrapper(DateTimeWrapper):
    def __init__(self, app):
        super().__init__(app, app.get_now().astimezone(app.AD.tz))

    def between(self, start_str, end_str):
        return self._app.now_is_between(start_str, end_str)
