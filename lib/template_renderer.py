from datetime import datetime

from jinja2 import Environment

from lib.helper import to_int, to_float, to_datetime, is_float, is_int


def safe_eval(value):
    try:
        return eval(value)
    except:
        return value


class TemplateRenderer:
    def __init__(self, app):
        self._app = app
        self._jinja_env = Environment()

        def get_state(entity_id, overrides={}):
            state = self._get_state(entity_id)
            return overrides.get(state, state)

        def get_state_attribute(entity_id, attribute):
            return self._get_state(entity_id, attribute=attribute)

        def is_state_attribute(entity_id, attribute, expected):
            value = get_state_attribute(entity_id, attribute)

            if value is None:
                return False

            return value == expected

        def get_friendly_name(entity_id):
            return self._get_state(entity_id, attribute="friendly_name")

        def format_date(date, format='%b %d'):
            if not isinstance(date, datetime):
                date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')

            return date.strftime(format)

        def get_age(date) -> str:
            def formatn(number: int, unit: str) -> str:
                """Add "unit" if it's plural."""
                if number == 1:
                    return "1 {}".format(unit)
                return "{:d} {}s".format(number, unit)

            def q_n_r(first: int, second: int):
                """Return quotient and remaining."""
                return first // second, first % second

            if not isinstance(date, datetime):
                date = to_datetime(date).replace(tzinfo=None)

            delta = datetime.utcnow() - date
            day = delta.days
            second = delta.seconds

            year, day = q_n_r(day, 365)
            if year > 0:
                return formatn(year, "year")

            month, day = q_n_r(day, 30)
            if month > 0:
                return formatn(month, "month")
            if day > 0:
                return formatn(day, "day")

            hour, second = q_n_r(second, 3600)
            if hour > 0:
                return formatn(hour, "hour")

            minute, second = q_n_r(second, 60)
            if minute > 0:
                return formatn(minute, "minute")

            return formatn(second, "second")

        def now_is_between(start_time, end_time):
            return self._now_is_between(start_time, end_time)

        self._jinja_env.globals['state'] = get_state
        self._jinja_env.globals['state_attr'] = get_state_attribute
        self._jinja_env.globals['is_state_attr'] = is_state_attribute
        self._jinja_env.globals['friendly_name'] = get_friendly_name
        self._jinja_env.globals['format_date'] = format_date
        self._jinja_env.globals['relative_time'] = get_age
        self._jinja_env.globals['now_is_between'] = now_is_between

        if hasattr(self._app, 'variables'):
            for name, value in self._app.variables.items():
                if name in self._jinja_env.globals:
                    raise ValueError('Variable {} already defined in template'.format(name))

                self._jinja_env.globals[name] = value

    def render(self, message, **kwargs):
        if self._should_render_template(message):
            template = self._jinja_env.from_string(message)
            rendered = template.render(**kwargs)

            if is_float(rendered):
                rendered = to_float(rendered)
            elif is_int(rendered):
                rendered = to_int(rendered)
            elif rendered.startswith('[') or rendered.startswith('{'):
                rendered = safe_eval(rendered)

            if self._should_render_template(rendered):
                rendered = self.render(rendered, **kwargs)

            if isinstance(rendered, str):
                rendered = rendered.strip()

            return rendered

        return message

    def _should_render_template(self, message):
        return isinstance(message, str) and ("{{" in message or "{%" in message)

    def _get_state(self, entity=None, **kwargs):
        return self._app.get_state(entity, **kwargs)

    def _now_is_between(self, start_time, end_time):
        return self._app.now_is_between(start_time, end_time)
