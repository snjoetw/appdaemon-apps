from datetime import datetime, timedelta

import googlemaps

from base_automation import BaseAutomation
from lib.core.monitored_callback import monitored_callback

BEST_ROUTE_NOTIFY_MESSAGE_TEMPLATE = 'Best route to work is via {} which ' \
                                     'takes about {} min. '

ALT_ROUTE_NOTIFY_MESSAGE_TEMPLATE = 'Another route is via {} which takes ' \
                                    'about {} min. '


class CommuteTimeMonitor(BaseAutomation):

    def initialize(self):
        self._handles_by_state_entity_id = {}
        self._configs = []
        self._api_key = self.cfg.value('google_travel_time_api_key')
        self._maps_api = googlemaps.Client(key=self._api_key)
        self._notify_entity_ids = self.cfg.list('notify_entity_id', [])
        self._presence_entity_id = self.cfg.value('presence_status_entity_id')
        self._start_time = self.cfg.value('start_time')
        self._end_time = self.cfg.value('end_time')

        self._route_configs = []
        for route_config in self.cfg.value('routes'):
            self._route_configs.append(RouteConfig(route_config))

        # self.run_every(self.run_every_handler, datetime.now(), 900)

    @monitored_callback
    def run_every_handler(self, time=None, **kwargs):
        if not self.should_monitor():
            return

        departure_time = datetime.now() + timedelta(minutes=10)
        routes = self.get_routes(departure_time)

        if not routes:
            return

        message = self.get_message(routes)
        self.log(message)

        for notify_entity_id in self._notify_entity_ids:
            self.call_service("notify/{}".format(notify_entity_id),
                              message=message)

    def get_message(self, routes):
        message = BEST_ROUTE_NOTIFY_MESSAGE_TEMPLATE.format(
            routes[0].name,
            routes[0].duration_in_min)

        if len(routes) > 1:
            message = message + ALT_ROUTE_NOTIFY_MESSAGE_TEMPLATE.format(
                routes[1].name,
                routes[1].duration_in_min)

        return message

    def get_routes(self, departure_time):
        routes = []

        for route_config in self._route_configs:
            legs = []

            for leg_config in route_config.leg_configs:
                leg = self.get_leg_result(leg_config, departure_time)
                if leg is None:
                    break

                legs.append(leg)

            if not legs:
                continue

            route = Route(route_config.name, legs)

            self.log('Route via {} takes about {} min'.format(
                route.name,
                route.duration_in_min))

            routes.append(route)

        if not routes:
            self.debug('Failed to get any route duration')
            return

        routes.sort(key=lambda r: r.duration)

        return routes

    def get_leg_result(self, leg_config, departure_time):
        result = self._maps_api.distance_matrix(
            leg_config['start'],
            leg_config['end'],
            mode=leg_config['travel_mode'],
            transit_mode=leg_config['transit_mode'],
            departure_time=departure_time)

        if result['status'] != 'OK':
            self.error('Received not OK response for {}'.format(leg_config))
            return None

        return Leg(
            result['origin_addresses'],
            result['destination_addresses'],
            result['rows'][0]['elements'][0]['duration']['value'],
        )

    def should_monitor(self):
        if not self.is_work_day():
            self.debug('Skipping ... not workday')
            return False

        if not self.is_home():
            self.debug('Skipping ... not home')
            return False

        if not self.is_in_monitoring_time():
            self.debug('Skipping ... not in monitoring time')
            return False

        return True

    def is_work_day(self):
        weekday = datetime.now().weekday()
        # Monday is 0 and Sunday is 6
        return weekday <= 4

    def is_home(self):
        presence_status = self.get_state(self._presence_entity_id)
        return presence_status != 'Away'

    def is_in_monitoring_time(self):
        return self.now_is_between(self._start_time, self._end_time)


class Route:
    def __init__(self, name, legs):
        self._name = name
        self._legs = legs

    @property
    def name(self):
        return self._name

    @property
    def duration(self):
        return sum(leg.duration for leg in self._legs)

    @property
    def duration_in_min(self):
        return round(self.duration / 60)


class Leg:
    def __init__(self, origin, destination, duration):
        self._origin = origin
        self._destination = destination
        self._duration = duration

    @property
    def origin(self):
        return self._origin

    @property
    def destination(self):
        return self._destination

    @property
    def duration(self):
        return self._duration

    @property
    def duration_in_min(self):
        return round(self.duration / 60)


class RouteConfig:

    def __init__(self, config):
        self._name = config['name']
        self._leg_configs = []
        start = config['origin']

        for destination in config['destinations']:
            travel_mode = destination['travel_mode']
            transit_mode = None

            if travel_mode == 'transit':
                transit_mode = 'subway'

            self._leg_configs.append({
                'start': start,
                'end': destination['destination'],
                'travel_mode': destination['travel_mode'],
                'transit_mode': transit_mode,
            })

            start = destination['destination']

    @property
    def name(self):
        return self._name

    @property
    def leg_configs(self):
        return self._leg_configs
