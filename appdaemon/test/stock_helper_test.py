import unittest

from lib.stock_helper import Quote
from test_helper import create_datetime

QUOTE_JSON = {
    "c": 261.74,
    "h": 263.31,
    "l": 260.68,
    "o": 261.07,
    "pc": 259.45,
    # February 25, 2021 12:00:00 AM GMT
    # February 24, 2021 4:00:00 PM GMT-08:00
    "t": 1614211200,
}


class StockQuoteTest(unittest.TestCase):

    def test_quote_json(self):
        current_time = create_datetime(2021, 2, 25, 7, 57, 4)
        quote = Quote(current_time, 'IBM', QUOTE_JSON)

        self.assertTrue(quote.symbol == 'IBM')
        self.assertTrue(quote.price == 261.74)
        self.assertTrue(quote.high == 263.31)
        self.assertTrue(quote.low == 260.68)
        self.assertTrue(quote.open == 261.07)
        self.assertTrue(quote.previous_close == 259.45)
        self.assertTrue(quote.timestamp.year == 2021)
        self.assertTrue(quote.timestamp.month == 2)
        self.assertTrue(quote.timestamp.day == 25)
        self.assertTrue(quote.change == 2.29)
        self.assertTrue(quote.change_percent == '1%')

    def test_quote_is_in_trading_time(self):
        current_time = create_datetime(2021, 2, 25, 7, 57, 4)

        quote = Quote(current_time, 'AAPL', QUOTE_JSON)
        self.assertTrue(quote.is_currently_trading)

    def test_quote_is_not_in_trading_time(self):
        current_time = create_datetime(2021, 2, 25, 13, 1, 5)
        QUOTE_JSON['t'] = current_time.timestamp()

        quote = Quote(current_time, 'AAPL', QUOTE_JSON)
        self.assertFalse(quote.is_currently_trading)

    def test_quote_is_different_in_trading_day(self):
        current_time = create_datetime(2021, 2, 26, 7, 58, 51)

        quote = Quote(current_time, 'AAPL', QUOTE_JSON)
        self.assertFalse(quote.is_currently_trading)
