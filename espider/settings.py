import json
import os


class BaseSetting(object):
    def __init__(self):
        self.max_thread = 10
        self.max_retry = 3
        self.wait_time = 0


class Setting(BaseSetting):
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

    def get(self, key, option=None):
        return self.__dict__.get(key, option)

    def items(self):
        return self.__dict__.items()

    def __repr__(self):
        return json.dumps(self.__dict__)
