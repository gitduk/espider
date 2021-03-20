import requests
import threading
from espider.parser.response import Response
from espider.settings import __REQUEST_KEYS__


class RequestThread(threading.Thread):
    __DEFAULT_THREAD_VALUE__ = [
        'name',
        'daemon'
    ]

    __DEFAULT_METHOD_VALUE__ = [
        'GET',
        'POST',
        'HEAD',
        'OPTIONS',
        'PUT',
        'PATCH',
        'DELETE'
    ]
    __DEFAULT_KEY__ = [
        'resp'  # 响应
        'priority'  # 请求优先级
        'use_session'  # 是否使用session
        'max_retry'  # 重试次数
    ]

    def __init__(self, url, method='', args=None, **kwargs):
        super().__init__()
        threading.Thread.__init__(self, name=kwargs.get('name'), daemon=kwargs.get('daemon'))

        # 必要参数
        self.url = url
        self.method = method.upper() or 'GET'
        assert self.method in self.__DEFAULT_METHOD_VALUE__, f'Invalid method {method}'

        # 请求参数
        self.request_kwargs = {key: value for key, value in kwargs.items() if key in __REQUEST_KEYS__}
        if self.request_kwargs.get('data') or self.request_kwargs.get('json'): self.method = 'POST'

        # 自定义参数
        self.response = None
        self.priority = kwargs.get('priority') or 0
        self.max_retry = kwargs.get('max_retry') or 0
        self.callback = kwargs.get('callback')
        self.args = args or ()

    def run(self):
        response = requests.request(method=self.method, url=self.url, **self.request_kwargs)

        if response.status_code != 200 and self.max_retry > 0:
            self.max_retry -= 1
            self.run()
            self.priority += 1
            msg = f'Retry-{self.priority}: [{self.method.upper()}] {response.url} {response.request.body or ""} {response.status_code}'
            print(msg)
        else:
            response_pro = Response(response)
            self.response = response_pro

            if self.args:
                if not isinstance(self.args, tuple): self.args = (self.args,)
                func_args = (_ for _ in self.args if not isinstance(_, dict))
                func_kwargs = [_ for _ in self.args if isinstance(_, dict)]
                func_kwargs = func_kwargs[0] if func_kwargs else {}
            else:
                func_args, func_kwargs = (), {}
            if self.callback: self.callback(response_pro, *func_args, **func_kwargs)

    def __repr__(self):
        return "<%s(%s, %s)>" % (self.__class__.__name__, self.name, self.priority)
