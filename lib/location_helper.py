import googlemaps

from lib.core.app_accessible import AppAccessible


class Location:
    def __init__(self, address_components, latitude, longitude):
        for component in address_components:
            if 'street_number' in component['types']:
                self._street_number = component['long_name']
            elif 'route' in component['types']:
                self._street_name = component['long_name']
            elif 'locality' in component['types']:
                self._city = component['long_name']
            elif 'administrative_area_level_1' in component['types']:
                self._province = component['long_name']
            elif 'country' in component['types']:
                self._country = component['long_name']
            elif 'postal_code' in component['types']:
                self._postal_code = component['long_name']
        self._latitude = latitude
        self._longitude = longitude

    @property
    def street(self):
        return self._street_number + ' ' + self._street_name

    @property
    def street_number(self):
        return self._street_number

    @property
    def street_name(self):
        return self._street_name

    @property
    def city(self):
        return self._city

    @property
    def province(self):
        return self._province

    @property
    def country(self):
        return self._country

    @property
    def postal_code(self):
        return self._postal_code

    @property
    def latitude(self):
        return self._latitude

    @property
    def longitude(self):
        return self._longitude

    def __repr__(self):
        return "{}(street={}, city={}, province={}, country={}, postal_code={}, latitude={}, longitude={})".format(
            self.__class__.__name__,
            self.street,
            self.city,
            self.province,
            self.country,
            self.postal_code,
            self.latitude,
            self.longitude)


class LocationFetcher(AppAccessible):
    def __init__(self, app, api_key):
        super().__init__(app)

        self.maps_api = googlemaps.Client(key=api_key)
        self._cache = {}

    def fetch_location(self, address) -> Location:
        if address in self._cache:
            return self._cache[address]

        self.debug('About to fetch location with address={}'.format(address))
        results = self.maps_api.geocode(
            address=address,
            components={'country': 'CA'})

        self.debug('Received geocoding response: {}'.format(results))

        latitude = results[0]['geometry']['location']['lat']
        longitude = results[0]['geometry']['location']['lng']
        location = Location(results[0]['address_components'], latitude, longitude)
        self._cache[address] = location

        return location
