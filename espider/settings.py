import json
import os
from pprint import pprint


class Setting(object):
    __setting_module_list__ = [
        'downloader', 'request'
    ]

    def __init__(self):
        try:
            # 加载用户配置
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    user_settings = json.load(f)
                    self.__dict__.update(user_settings)

        except Exception as e:
            print(f'load setting failed ... {e}')

    def get(self, key, option=None):
        return self.__dict__.get(key, option)

    def __repr__(self):
        pprint({k: v for k, v in self.__dict__.items() if k in self.__setting_module_list__})
        return ''
