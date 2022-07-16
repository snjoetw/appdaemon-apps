from datetime import timedelta, datetime
from unittest import TestCase, mock
from unittest.mock import Mock, patch

import briefing_helper
import calendar_helper
from briefing_helper import CalendarBriefingProvider
from calendar_helper import CalendarEvent
from lib.context import Context, PartsOfDay
from test_helper import create_datetime


def create_event(title, description, location, start_time):
    end_time = start_time + timedelta(minutes=30)
    return CalendarEvent({
        'end': {
            'dateTime': end_time.strftime('%Y-%m-%dT%H:%M:%S%z')
        },
        'start': {
            'dateTime': start_time.strftime('%Y-%m-%dT%H:%M:%S%z')
        },
        'location': location,
        'summary': title,
        'description': description,
    })


REGULAR_EVENT_1 = create_event('Zoom Meeting', 'zoom-url', 'Home', create_datetime(2021, 2, 25, 10, 0, 0))
REGULAR_EVENT_2 = create_event('Lunch time', None, 'Home', create_datetime(2021, 2, 25, 12, 5, 0))
REGULAR_EVENT_3 = create_event('Nap time', 'play music', None, create_datetime(2021, 2, 25, 13, 30, 0))

TODAY_GARBAGE_COLLECTION_EVENT = create_event('Garbage Collection', '', None, create_datetime(2021, 2, 25, 7, 0, 0))
TODAY_RECYCLE_COLLECTION_EVENT = create_event('Recycling Collection', '', None, create_datetime(2021, 2, 25, 7, 0, 0))

TOMORROW_GARBAGE_COLLECTION_EVENT = create_event('Garbage Collection', '', None, create_datetime(2021, 2, 26, 7, 0, 0))
TOMORROW_RECYCLE_COLLECTION_EVENT = create_event('Recycling Collection', '', None,
                                                 create_datetime(2021, 2, 26, 7, 0, 0))


def create_provider(regular_events=[], waste_collection_event=None):
    events_fetcher = Mock()
    events_fetcher.fetch_regular_events.return_value = regular_events
    events_fetcher.fetch_waste_collection_event.return_value = waste_collection_event

    app = Mock(**{'variables': {}})
    provider = CalendarBriefingProvider(app, {})
    provider.events_fetcher = events_fetcher
    return provider


def expect_now(year, month, day, hour, minute, second):
    now = create_datetime(year, month, day, hour, minute, second, None)
    briefing_helper.datetime.today = mock.Mock(return_value=now.date())
    briefing_helper.datetime.now = mock.Mock(return_value=now)

    calendar_helper.datetime.today = mock.Mock(return_value=now)
    calendar_helper.datetime.now = mock.Mock(return_value=now)


class StockPriceProviderTest(TestCase):

    @patch.object(briefing_helper, 'datetime', Mock(wraps=datetime))
    @patch.object(calendar_helper, 'datetime', Mock(wraps=datetime))
    def test_morning_briefing_with_today_s_appointments_only(self):
        expect_now(2021, 2, 25, 11, 57, 4)
        provider = create_provider(regular_events=[REGULAR_EVENT_1, REGULAR_EVENT_2, REGULAR_EVENT_3])

        text = provider.briefing(Context(PartsOfDay.MORNING))

        self.assertEqual(
            'Today you have 2 appointments, <break time=".3s" /> at 12:05 PM<break time=".2s" />Lunch time'
            '<break time=".2s" /> and <break time=".3s" /> at 01:30 PM<break time=".2s" />Nap time',
            text)

    @patch.object(briefing_helper, 'datetime', Mock(wraps=datetime))
    @patch.object(calendar_helper, 'datetime', Mock(wraps=datetime))
    def test_morning_briefing_with_garbage_collection_and_today_s_appointments(self):
        expect_now(2021, 2, 25, 7, 57, 4)
        provider = create_provider(regular_events=[REGULAR_EVENT_1, REGULAR_EVENT_2, REGULAR_EVENT_3],
                                   waste_collection_event=TODAY_GARBAGE_COLLECTION_EVENT)

        text = provider.briefing(Context(PartsOfDay.MORNING))

        self.assertEqual('Today is Garbage Collection day. <break time=".3s" />You also have 3 other appointments '
                         'Today, <break time=".3s" /> at 10:00 AM<break time=".2s" />Zoom Meeting, '
                         '<break time=".3s" /> at 12:05 PM<break time=".2s" />Lunch time<break time=".2s" /> and '
                         '<break time=".3s" /> at 01:30 PM<break time=".2s" />Nap time',
                         text)

    @patch.object(briefing_helper, 'datetime', Mock(wraps=datetime))
    @patch.object(calendar_helper, 'datetime', Mock(wraps=datetime))
    def test_morning_briefing_with_today_s_appointments_and_tomorrow_s_garbage_collection(self):
        expect_now(2021, 2, 25, 7, 57, 4)
        provider = create_provider(regular_events=[REGULAR_EVENT_1, REGULAR_EVENT_2, REGULAR_EVENT_3],
                                   waste_collection_event=TOMORROW_GARBAGE_COLLECTION_EVENT)

        text = provider.briefing(Context(PartsOfDay.MORNING))

        self.assertEqual('Today you have 3 appointments, <break time=".3s" /> at 10:00 AM<break time=".2s" />Zoom '
                         'Meeting, <break time=".3s" /> at 12:05 PM<break time=".2s" />Lunch time<break time=".2s" /> '
                         'and <break time=".3s" /> at 01:30 PM<break time=".2s" />Nap time.<break time=".3s" />Also, '
                         'tomorrow is Garbage Collection day',
                         text)

    @patch.object(briefing_helper, 'datetime', Mock(wraps=datetime))
    @patch.object(calendar_helper, 'datetime', Mock(wraps=datetime))
    def test_evening_briefing_with_recycling_collection_and_tomorrow_s_appointments(self):
        expect_now(2021, 2, 25, 7, 57, 4)
        provider = create_provider(regular_events=[REGULAR_EVENT_1, REGULAR_EVENT_2, REGULAR_EVENT_3],
                                   waste_collection_event=TOMORROW_RECYCLE_COLLECTION_EVENT)

        text = provider.briefing(Context(PartsOfDay.EVENING))

        self.assertEqual('Tomorrow is Recycling Collection day. <break time=".3s" />You also have 3 other '
                         'appointments Tomorrow, <break time=".3s" /> the first event is <break time=".3s" /> at '
                         '10:00 AM<break time=".2s" />Zoom Meeting',
                         text)

    @patch.object(briefing_helper, 'datetime', Mock(wraps=datetime))
    @patch.object(calendar_helper, 'datetime', Mock(wraps=datetime))
    def test_night_briefing_with_garbage_collection_and_tomorrow_s_appointment(self):
        expect_now(2021, 2, 25, 7, 57, 4)
        provider = create_provider(regular_events=[REGULAR_EVENT_1],
                                   waste_collection_event=TOMORROW_GARBAGE_COLLECTION_EVENT)

        text = provider.briefing(Context(PartsOfDay.NIGHT))

        self.assertEqual('Tomorrow is Garbage Collection day. <break time=".3s" />You also have 1 other appointment '
                         'Tomorrow, <break time=".3s" /> at 10:00 AM<break time=".2s" />Zoom Meeting',
                         text)
