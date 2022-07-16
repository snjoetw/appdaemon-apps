import appdaemon.plugins.mqtt.mqttapi as mqtt
from enum import Enum
from typing import List

from base_automation import BaseAutomation
from lib.core.component import Component
from lib.core.monitored_callback import monitored_callback

BASE_TOPIC = 'app/notification/'


class Handler(Component):
    def __init__(self, app, app_package):
        super().__init__(app, {})
        self._app_package = app_package

    @property
    def app_package(self):
        return self._app_package

    def handle(self, title, text, source):
        self.log('Handling title={}, text={}, source={} with handler={}'.format(title, text, source, self))
        self._do_handle(title, text, source)

    def _do_handle(self, title, text, source):
        pass


class MobileAppNotificationHandler(BaseAutomation):
    _handlers: List[Handler]

    def initialize(self):
        self._handlers = [
            # TelusAlarmHandler(self),
            # NestHandler(self),
            UberEatsHandler(self),
            DoorDashHandler(self)]

        for notification_entity_id in self.cfg.list('notification_entity_id'):
            self.listen_state(self._notification_state_change_handler, notification_entity_id)

    @monitored_callback
    def _notification_state_change_handler(self, entity, attribute, old, new, kwargs):
        app_package = self.get_state(entity, attribute='package')
        for handler in self._handlers:
            if handler.app_package == app_package:
                return handler.handle(
                    self.get_state(entity, attribute='android.title'),
                    self.get_state(entity, attribute='android.text'),
                    entity)


class TelusAlarmHandler(Handler):
    def __init__(self, app):
        super().__init__(app, 'com.alarm.alarmmobile.android.telus')

    def _do_handle(self, title, text, source):
        telus_alarm_state = self._figure_alarm_state(title)
        if telus_alarm_state is None:
            self.error('No alarm state defined for title={}, text={}'.format(title, text))
            return

        current_alarm = self.get_state('alarm_control_panel.home_alarm', attribute='all')
        current_alarm_state = current_alarm['state']
        if current_alarm_state == telus_alarm_state:
            self.log('Alarm state is already {}, skipping title={}, text={}'.format(current_alarm_state, title, text))
            return

        alarm_attributes = current_alarm.get('attributes', {})
        alarm_attributes['changed_by'] = 'Telus SmartHome'

        # setting state before calling service to alarm_state_change_events to filter by changed_by attribute
        self.set_state('alarm_control_panel.home_alarm', state=telus_alarm_state, attributes=alarm_attributes)
        self.app.sleep(0.5)
        self.call_service(self._figure_service_name(title), entity_id='alarm_control_panel.home_alarm')

    @staticmethod
    def _figure_alarm_state(title):
        if 'Home Disarmed' in title:
            return 'disarmed'
        elif 'Home Armed Stay' in title:
            return 'armed_home'
        elif 'Home Armed Away' in title:
            return 'armed_away'
        return None

    @staticmethod
    def _figure_service_name(title):
        if 'Home Disarmed' in title:
            return 'alarm_control_panel/alarm_disarm'
        elif 'Home Armed Stay' in title:
            return 'alarm_control_panel/alarm_arm_home'
        elif 'Home Armed Away' in title:
            return 'alarm_control_panel/alarm_arm_away'
        return None


AD_EVENT_NEST = 'ad.nest_event'


class NestEventType(Enum):
    PERSON = 'person'
    PERSON_TALKING = 'person_talking'
    MOTION = 'motion'
    PACKAGE_LEFT = 'package_left'
    PACKAGE_PICKED_UP = 'package_picked_up'
    DOORBELL = 'doorbell'
    CAMERA_OFFLINE = 'camera_offline'
    KNOWN_FACE_DETECTED = 'known_face_detected'
    UNFAMILIAR_FACE = 'Unfamiliar face?'
    SOUND = 'sound'
    DOG_BARKING = 'Dog barking'


HOME_JOE = 'Joe'
HOME_DAD = 'Dad'


class NestHandler(Handler):
    def __init__(self, app):
        super().__init__(app, '')

    def _do_handle(self, title, text, source):
        event, location = title.split(' • ')
        if not event or not location:
            self.log('Unable to handle title={}'.format(title))
            return

        home = self._figure_home(location)
        event_type = self._figure_event_type(event)
        if event_type:
            return self._handle_event(event_type, home, location)

        if text.startswith('Your camera thinks it spotted a familiar face'):
            return self._handle_event(NestEventType.KNOWN_FACE_DETECTED, home, location, face_detected=event)

        self.warn('Unsupported event, not handling title={}, text={}'.format(title, text))

    def _handle_event(self, event_type, home, location, **kwargs):
        self.log('Handling {} event, home={}, location={}, kwargs={}'.format(event_type, home, location, kwargs))
        self.app.fire_event(AD_EVENT_NEST, event_type=event_type.value, home=home, location=location, **kwargs)

    @staticmethod
    def _figure_event_type(event):
        if event is None:
            return

        try:
            return NestEventType(event.lower().replace(' ', '_'))
        except ValueError:
            return

    @staticmethod
    def _figure_home(location):
        if 'Dad' in location:
            return HOME_DAD
        return HOME_JOE


AD_EVENT_FOOD_DELIVERY = 'ad.food_delivery_event'


class FoodDeliveryEventType(Enum):
    ORDER_DELIVERED = 'order_delivered'
    ORDER_ALMOST_DELIVERED = 'order_almost_delivered'
    ORDER_ON_THE_MOVE = 'order_on_the_move'
    PREPARING_ORDER = 'preparing_order'
    ORDER_READY_FOR_PICKUP = 'order_ready_for_pickup'


class UberEatsHandler(Handler):
    def __init__(self, app):
        super().__init__(app, 'com.ubercab.eats')

    def _do_handle(self, title, text, source):
        event_type = self._figure_event_type(text)
        if not event_type:
            self.warn('Unsupported event, not handling title={}, text={}'.format(title, text))
            return

        self.log('Handling {} event, title={}, text={}'.format(event_type, title, text))
        self.app.fire_event(AD_EVENT_FOOD_DELIVERY, event_type=event_type.value, service_name='Uber Eats')

    @staticmethod
    def _figure_event_type(text):
        if 'Grab your order at the door' in text:
            return FoodDeliveryEventType.ORDER_DELIVERED
        elif 'time to drop off your order' in text or 'moment to leave your order at the door' in text:
            return FoodDeliveryEventType.ORDER_ALMOST_DELIVERED
        elif 'has your order' in text:
            return FoodDeliveryEventType.ORDER_ON_THE_MOVE
        elif 'is preparing your order' in text or 'is working on your order' in text:
            return FoodDeliveryEventType.PREPARING_ORDER
        elif 'Time to pick up your order' in text:
            return FoodDeliveryEventType.ORDER_READY_FOR_PICKUP
        return None


class DoorDashHandler(Handler):
    def __init__(self, app):
        super().__init__(app, '')

    def _do_handle(self, title, text, source):
        event_type = self._figure_event_type(text)
        if not event_type:
            self.warn('Unsupported event, not handling title={}, text={}'.format(title, text))
            return

        self.log('Handling {} event, title={}, text={}'.format(event_type, title, text))
        self.app.fire_event(AD_EVENT_FOOD_DELIVERY, event_type=event_type.value, service_name='DoorDash')

    @staticmethod
    def _figure_event_type(text):
        if 'your order has been picked up' in text:
            return FoodDeliveryEventType.ORDER_ON_THE_MOVE
        elif 'has confirmed your order from DoorDash' in text:
            return FoodDeliveryEventType.PREPARING_ORDER
        elif 'dropped off your order.' in text:
            return FoodDeliveryEventType.ORDER_DELIVERED
        elif 'is approaching with your order from' in text:
            return FoodDeliveryEventType.ORDER_ALMOST_DELIVERED
        return None
