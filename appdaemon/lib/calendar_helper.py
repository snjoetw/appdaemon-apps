from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List

import requests

from lib.core.app_accessible import AppAccessible


class CalendarEvent:
    def __init__(self, json):
        self._end_time = from_datetime_str(json.get('end').get('dateTime'))
        self._start_time = from_datetime_str(json.get('start').get('dateTime'))
        self._location = json.get('location')
        self._title = json.get('summary')
        self._description = json.get('description')

        if self._start_time is None:
            self._start_time = from_date_str(json.get('start').get('date'))

        if self._end_time is None:
            self._end_time = from_date_str(json.get('end').get('date'))

        delta = self.end_time - self.start_time
        self._is_all_day = delta.days >= 1

    @property
    def end_time(self):
        return self._end_time

    @property
    def start_time(self):
        return self._start_time

    @property
    def location(self):
        return self._location

    @property
    def title(self):
        return self._title

    @property
    def description(self):
        return self._description

    @property
    def is_all_day(self):
        return self._is_all_day

    @property
    def is_today(self):
        if not self.start_time:
            return False
        return self.start_time.date() <= datetime.today().date() <= self.end_time.date();

    @property
    def is_tomorrow(self):
        if not self.start_time:
            return False
        tomorrow = datetime.today() + timedelta(days=1)
        return self.start_time.date() == tomorrow.date()

    def __repr__(self):
        return "{}(title={}, location={}, start_time={}, end_time={}, is_all_day={}, is_today={}, is_tomorrow={})".format(
            self.__class__.__name__,
            self.title,
            self.location,
            self.start_time,
            self.end_time,
            self.is_all_day,
            self.is_today,
            self.is_tomorrow)


def is_no_school_event(event: CalendarEvent):
    if event is None or not event.title or not event.is_today:
        return False

    if has_no_school_keyword(event.title):
        return True
    elif has_no_school_keyword(event.description):
        return True

    return False


def has_no_school_keyword(value: str):
    if not value:
        return False

    value = value.lower()
    if 'pro – d day' in value:
        return True
    if 'pro d day' in value:
        return True
    if 'no school' in value:
        return True
    elif 'students do not attend' in value:
        return True
    elif 'thanksgiving day' in value:
        return True
    elif 'christmas break' in value:
        return True
    elif 'spring break' in value:
        return True

    return False


def create_date_range_params(start_date, end_date):
    if end_date is None:
        end_date = start_date

    # '2019-08-11T00:00:00Z'
    # time.tzname
    return {
        'start': datetime.combine(start_date, datetime.min.time())
            .astimezone(tz=timezone.utc)
            .isoformat(),
        'end': datetime.combine(end_date + timedelta(days=1),
                                datetime.min.time())
            .astimezone(tz=timezone.utc)
            .isoformat(),
    }


def from_datetime_str(date_str):
    if not date_str:
        return None

    date_str = date_str.replace('-07:00', '-0700').replace('-08:00', '-0800')
    return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S%z')


def from_date_str(date_str):
    if not date_str:
        return None

    date_str += 'T00:00:00Z'

    return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ').astimezone()


class CalendarEventFetcher(AppAccessible):
    def __init__(self, app, api_base_url, api_token):
        super().__init__(app)

        self.api_headers = {
            'Authorization': api_token,
            'Content-Type': 'application/json'
        }
        self.api_url = "{}/api/calendars/".format(api_base_url)

    def fetch_upcoming_event(self, calendar_entity_id, start_date, end_date=None) -> CalendarEvent:
        regular_events = self.fetch_regular_events(calendar_entity_id, start_date, end_date)

        self.debug('Found {} events'.format(len(regular_events)))
        now = datetime.now()
        filtered = [e for e in regular_events if e.start_time.replace(tzinfo=None) > now and e.location]

        self.debug('Found {} future events'.format(len(filtered)))

        if not filtered:
            return None

        return filtered[0]

    def fetch_regular_events(self, calendar_entity_id, start_date, end_date=None) -> List[CalendarEvent]:
        events = self.fetch_events(calendar_entity_id, start_date, end_date)
        events.sort(key=lambda e: e.start_time)

        return [e for e in events if not e.is_all_day]

    def fetch_all_day_events(self, calendar_entity_id, start_date, end_date=None) -> List[CalendarEvent]:
        events = self.fetch_events(calendar_entity_id, start_date, end_date)
        events.sort(key=lambda e: e.start_time)

        return [e for e in events if e.is_all_day]

    def fetch_events(self, calendar_entity_id, start_date, end_date=None) -> List[CalendarEvent]:
        api_url = self.api_url + calendar_entity_id
        params = create_date_range_params(start_date, end_date)
        self.debug(
            'About to call API with url={}, params={}, headers={}'.format(
                api_url,
                params,
                self.api_headers,
            ))
        response = requests.get(
            api_url,
            params=params,
            headers=self.api_headers)

        self.debug('Received API response={}, json={}'.format(response, response.json()))

        response.raise_for_status()

        return [CalendarEvent(json_event) for json_event in response.json()]

    def fetch_waste_collection_event(self, calendar_entity_id, date) -> CalendarEvent:
        events = self.fetch_events(calendar_entity_id, date, date + timedelta(days=1))
        events.sort(key=lambda e: e.start_time)

        events_by_type = {}

        for e in events:
            if 'Garbage Collection' in e.title:
                events_by_type[WasteCollectionType.GARBAGE] = e
            if 'Recycling Collection' in e.title:
                events_by_type[WasteCollectionType.RECYCLING] = e

        if WasteCollectionType.GARBAGE in events_by_type:
            return events_by_type[WasteCollectionType.GARBAGE]

        if WasteCollectionType.RECYCLING in events_by_type:
            return events_by_type[WasteCollectionType.RECYCLING]

        return None


class WasteCollectionType(Enum):
    GARBAGE = 1
    RECYCLING = 2
