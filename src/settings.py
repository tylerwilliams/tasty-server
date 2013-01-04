import os
import logging
import ConfigParser

logger = logging.getLogger(__name__)
CONFIG_FILE_DEFAULT_PATH = "/etc/tasty.conf"
CONFIG_FILE_SECTION_NAME = "api"

class SettingsManager(object):
    def __init__(self, filepath=None, defaults=None, overrides=None):
        self.filepath = self.findconf(filepath)
        self.__settings__ = defaults or {}
        self.overrides = overrides or {}
        self.reloadconf()
        
    def findconf(self, filepath):
        if filepath and os.path.exists(filepath):
            return filepath
        elif os.path.exists(CONFIG_FILE_DEFAULT_PATH):
            logger.warning("falling back to default config file at %s", CONFIG_FILE_DEFAULT_PATH)
            return CONFIG_FILE_DEFAULT_PATH
        else:
            return None

    def get(self, setting_name):
        return self.__settings__.get(setting_name)
    
    def reloadconf(self):
        if self.filepath:
            config = ConfigParser.SafeConfigParser()
            config.read(self.filepath)
            self.__settings__.update(dict(config.items(CONFIG_FILE_SECTION_NAME)))
        self.__settings__.update(self.overrides)
    
    # could tie reloadconf to a signal if we wanted, and then get new settings in our app
    # without having to restart the process
    
"""
These settings can be overridden with a config file at
CONFIG_FILE_PATH. Here's an example of a config file:

file: /etc/tasty.conf
############################################################
[api]
cat = dog
API_KEY = 1234
############################################################
"""
