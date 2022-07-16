import unittest
from unittest.mock import Mock

from mobile_app_notification_handler import NestHandler, AD_EVENT_NEST


def create_handler(app):
    return NestHandler(app)


class TestNestHandler(unittest.TestCase):

    def test_known_face_detected_event(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle('Joe • Front Door\nYour camera thinks it spotted a familiar face.')
        app.fire_event.assert_called_once_with(AD_EVENT_NEST,
                                               event_type='known_face_detected',
                                               location='Front Door',
                                               face_detected='Joe')

    def test_package_picked_up_event(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle(
            'Package picked up • Front Door\nYour camera thinks it saw a package retrieved.')
        app.fire_event.assert_called_once_with(AD_EVENT_NEST, event_type='package_picked_up', location='Front Door')

    def test_person_event(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle('Person • Front Door Zone\nYour Front Door camera spotted someone.')
        app.fire_event.assert_called_once_with(AD_EVENT_NEST, event_type='person', location='Front Door Zone')

    def test_person_talking_event(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle('Person talking • Front Yard\nYour camera thinks it heard someone.')
        app.fire_event.assert_called_once_with(AD_EVENT_NEST, event_type='person_talking', location='Front Yard')

    def test_motion_event(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle('Motion • Backyard Zone\nYour Backyard camera noticed some activity.')
        app.fire_event.assert_called_once_with(AD_EVENT_NEST, event_type='motion', location='Backyard Zone')

    def test_camera_offline_event(self):
        app = Mock(**{'variables': {}})
        create_handler(app).handle('Camera offline • Backyard\nIt\'s been offline for 10 minutes.')
        app.fire_event.assert_called_once_with(AD_EVENT_NEST, event_type='camera_offline', location='Backyard')
