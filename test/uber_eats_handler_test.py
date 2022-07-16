import unittest
from unittest.mock import Mock

from mobile_app_notification_handler import UberEatsHandler, AD_EVENT_FOOD_DELIVERY


def create_handler(app):
    return UberEatsHandler(app)


class TestUberEatsHandler(unittest.TestCase):

    def test_order_delivered(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle(
            'Uber Eats\nIt’s here! Grab your order at the door, then don’t forget to rate and tip.')
        app.fire_event.assert_called_once_with(AD_EVENT_FOOD_DELIVERY, event_type='order_delivered')

    def test_order_almost_delivered(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle(
            'Uber Eats\n☝️⏱ Give Roger a moment to leave your order at the door. You’ll get an alert when it’s there.')
        app.fire_event.assert_called_once_with(AD_EVENT_FOOD_DELIVERY, event_type='order_almost_delivered')

    def test_order_on_the_move(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle(
            'Uber Eats\nYour order is on the move! There’s no need to meet—you’ll get an alert when it’s delivered.')
        app.fire_event.assert_called_once_with(AD_EVENT_FOOD_DELIVERY, event_type='order_on_the_move')

    def test_preparing_order(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle(
            'Uber Eats\nGong Cha -New West is preparing your order. Thank you for supporting restaurants.')
        app.fire_event.assert_called_once_with(AD_EVENT_FOOD_DELIVERY, event_type='preparing_order')

    def test_order_ready_for_pickup(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle(
            'Uber Eats\nIt’s ready! Time to pick up your order. For everyone’s safety, don’t forget a mask.')
        app.fire_event.assert_called_once_with(AD_EVENT_FOOD_DELIVERY, event_type='order_ready_for_pickup')
