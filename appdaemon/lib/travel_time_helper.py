import googlemaps

from lib.core.app_accessible import AppAccessible


class TravelTimeFetcher(AppAccessible):
    def __init__(self, app, api_key):
        super().__init__(app)

        self.maps_api = googlemaps.Client(key=api_key)

    def fetch_travel_time(self, origin, destination, travel_mode,
                          departure_time=None,
                          transit_mode=None):
        result = self.maps_api.distance_matrix(
            origin,
            destination,
            mode=travel_mode,
            transit_mode=transit_mode,
            departure_time=departure_time)

        if result['status'] != 'OK':
            self.error('Received not OK response: {}'.format(result))
            return None

        self.debug('Received distance_matrix response: {}'.format(result))

        return TravelTime(
            result['origin_addresses'][0],
            result['destination_addresses'][0],
            result['rows'][0]['elements'][0]['duration_in_traffic']['value'],
        )


class TravelTime:
    def __init__(self, origin, destination, duration):
        self._origin = origin
        self._destination = destination
        self._duration = duration
        self._distance = 0

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

    @property
    def distance(self):
        return self._distance
