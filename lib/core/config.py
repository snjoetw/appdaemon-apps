from lib.helper import to_int, to_float
from lib.template_renderer import TemplateRenderer


class Config:
    def __init__(self, app, config_dict):
        self._template_renderer = TemplateRenderer(app)
        self._config_dict = config_dict
        self._trigger_info = None

    @property
    def trigger_info(self):
        return self._trigger_info

    @trigger_info.setter
    def trigger_info(self, value):
        self._trigger_info = value

    def raw(self, key, default=None):
        return self._config_dict.get(key, default)

    def value(self, key, default=None, required=False):
        raw = self.raw(key)
        if raw is None:
            if required:
                raise ValueError('Missing config value: {}'.format(key))
            return default

        if isinstance(raw, dict):
            return self._to_dict(raw)
        elif isinstance(raw, list):
            return self._to_list(raw)

        return self._to_template_value(raw)

    def int(self, key, default=None):
        value = self.value(key)
        return to_int(value, default)

    def float(self, key, default=None):
        value = self.value(key)
        return to_float(value, default)

    def _to_dict(self, dict_value):
        applied = {}
        for k, v in dict_value.items():
            if isinstance(v, dict):
                applied[k] = self._to_dict(v)
            else:
                applied[k] = self._to_template_value(v)

        return applied

    def _to_list(self, list_value):
        applied = []
        for value in list_value:
            applied.append(self._to_template_value(value))
        return applied

    def list(self, key, default=None):
        value = self.value(key)
        if value is None:
            return default

        if isinstance(value, list):
            return self._flatten_list_config(value)

        return [value]

    def _flatten_list_config(self, config_value):
        values = []
        for value in config_value:
            if isinstance(value, list):
                values.extend(self._flatten_list_config(value))
            else:
                values.append(self._to_template_value(value))

        return values

    def _to_template_value(self, raw):
        rendered = self._template_renderer.render(raw, trigger_info=self._trigger_info)

        return rendered

    def __repr__(self):
        return "{}(config={})".format(
            self.__class__.__name__,
            self._config_dict)
