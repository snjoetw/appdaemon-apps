import traceback

from base_automation import BaseAutomation


def monitored_callback(callback):
    def inner(*args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except Exception as e:
            app: BaseAutomation = args[0]
            app.error('Exception thrown in callback: {}\n{}'.format(e, traceback.format_exc()))

    return inner
