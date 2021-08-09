import json
import os
from espider.network import Downloader, Request


class DefaultSetting(object):
    def __init__(self):
        self.max_thread = 10
        self.max_retry = 0
        self.wait_time = 0
        self.close_countdown = 3
        self.distribute_item = True


class Settings(DefaultSetting):
    __settings__ = [
        *Downloader.__settings__,
        *Request.__settings__
    ]

    def __init__(self):
        super().__init__()

        try:
            # 加载用户配置
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    user_settings = json.load(f)
                    self.__dict__.update(user_settings)

        except Exception as e:
            print(f'load setting failed ... {e}')
        else:
            for k in self.__settings__:
                if k not in self.__dict__.keys():
                    self.__dict__[k] = None

    def get(self, key, option=None):
        return self.__dict__.get(key, option)

    def items(self):
        return self.__dict__.items()

    def set(self, key, value):
        if key in self.__settings__:
            self.__dict__[key] = value
        else:
            print(f'Warning ... Invalid setting: {key}:{value}')

    def __repr__(self):
        return json.dumps(self.__dict__)
