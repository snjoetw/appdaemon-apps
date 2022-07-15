import appdaemon.plugins.hass.hassapi as hass


class AppdaemonStatusHandler(hass.Hass):
    def initialize(self):
        self.register_endpoint(self._event_change_handler, 'appdaemon_status')

    def _event_change_handler(self, data, kwargs):
        app_count = len(self.AD.app_management.objects)
        response = {
            "app_count": app_count
        }

        return response, 200
