import os

import appdaemon.plugins.hass.hassapi as hass

APPDAEMON_DIR = '/config/appdaemon/appdaemon'
DEFINITION_DIR = APPDAEMON_DIR + '/configurations/'
MERGED_APP_FILEPATH = APPDAEMON_DIR + '/apps.yaml'

FILE_CONTENT_DIVIDER = '###############################################################################\n' \
                       '# M E R G E D  F R O M  {}\n' \
                       '###############################################################################\n\n';


def _filename_comparator(filename):
    splitted = filename.split('_', 1)
    return tuple(-splitted[0], splitted[1])


def write(source_filename, destination):
    destination.write(FILE_CONTENT_DIVIDER.format(source_filename));

    with open(DEFINITION_DIR + source_filename, 'r') as source:
        destination.write(source.read())

    destination.write('\n\n\n\n');


class AppConfigurationMonitor(hass.Hass):
    def initialize(self):
        self.listen_event(self._event_change_handler, 'folder_watcher')

    def _event_change_handler(self, event_name, data, kwargs):
        self.log('{}'.format(data))
        changed_filename = data.get('file', '')

        if not changed_filename.endswith('yaml'):
            return

        self.log('Changes detected on {}, about to merge files in {}'.format(changed_filename, DEFINITION_DIR))

        filenames = sorted(os.listdir(DEFINITION_DIR))
        variable_filenames = [f for f in filenames if f.startswith('var')]
        filenames = [f for f in filenames if f not in variable_filenames]

        self.log(variable_filenames)
        self.log(filenames)

        with open(MERGED_APP_FILEPATH, 'w') as destination:
            for filename in variable_filenames:
                write(filename, destination)

            for filename in filenames:
                write(filename, destination)

        self.log('Merged {} files into {}'.format(len(filename), MERGED_APP_FILEPATH))
