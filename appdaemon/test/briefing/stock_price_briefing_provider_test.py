from unittest import TestCase

from briefing_helper import to_stock_current_price_briefing_text, to_stock_closed_price_briefing_text
from stock_helper import Quote
from test_helper import create_datetime

# 1614556800 => Monday, March 1, 2021 12:00:00 AM
QUOTES_JSON = {
    'AAPL': {'c': 127.79, 'h': 127.93, 'l': 122.79, 'o': 123.75, 'pc': 121.26, 't': 1614556800},
    'TSLA': {'c': 718.43, 'h': 872, 'l': 685.05, 'o': 690.11, 'pc': 675.5, 't': 1614556800},
    'SQ': {'c': 241, 'h': 241.7194, 'l': 232.1001, 'o': 238.11, 'pc': 230.03, 't': 1614556800},
}


def create_quotes(current_time):
    quotes = []
    for symbol, quote_json in QUOTES_JSON.items():
        quotes.append(Quote(current_time, symbol, quote_json))
    return quotes


class StockPriceProviderTest(TestCase):

    def test_current_price_briefing_text(self):
        current_time = create_datetime(2021, 3, 1, 6, 37, 17)

        text = to_stock_current_price_briefing_text(create_quotes(current_time))
        self.assertEqual(text,
                         'Currently, Apple is up 5.4%, to $127.79<break time=".2s" />,'
                         ' Tesla is up 6.4%, to $718.43<break time=".2s" />'
                         ' and SQ is up 4.8%, to $241<break time=".2s" />')

    def test_today_closed_price_briefing_text(self):
        current_time = create_datetime(2021, 3, 1, 13, 13, 59)

        text = to_stock_closed_price_briefing_text(current_time, create_quotes(current_time))
        self.assertEqual(text,
                         'Today, Apple was up 5.4%, to $127.79<break time=".2s" />,'
                         ' Tesla was up 6.4%, to $718.43<break time=".2s" />'
                         ' and SQ was up 4.8%, to $241<break time=".2s" />')

    def test_yesterday_closed_price_briefing_text(self):
        current_time = create_datetime(2021, 3, 2, 6, 13, 59)

        text = to_stock_closed_price_briefing_text(current_time, create_quotes(current_time))
        self.assertEqual(text,
                         'Yesterday, Apple was up 5.4%, to $127.79<break time=".2s" />,'
                         ' Tesla was up 6.4%, to $718.43<break time=".2s" />'
                         ' and SQ was up 4.8%, to $241<break time=".2s" />')

    def test_last_monday_closed_price_briefing_text2(self):
        current_time = create_datetime(2021, 3, 5, 6, 13, 59)

        text = to_stock_closed_price_briefing_text(current_time, create_quotes(current_time))
        self.assertEqual(text,
                         'Last Monday, Apple was up 5.4%, to $127.79<break time=".2s" />,'
                         ' Tesla was up 6.4%, to $718.43<break time=".2s" />'
                         ' and SQ was up 4.8%, to $241<break time=".2s" />')
