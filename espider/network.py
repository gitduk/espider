import time
from collections.abc import Generator, Iterable
import threading
from queue import Queue
import urllib3
from copy import deepcopy
from espider.default_settings import REQUEST_KEYS, DEFAULT_METHOD_VALUE
from espider.extensions import _load_extensions
from espider.parser.response import Response
from espider.utils.tools import args_split, PriorityQueue
import espider.utils.requests as requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Request(threading.Thread):
    __settings__ = [
        'max_retry'
    ]
    __DEFAULT_THREAD_VALUE__ = [
        'name',
        'daemon'
    ]

    def __init__(self, url, method='', args=None, **kwargs):
        super().__init__()
        threading.Thread.__init__(self, name=kwargs.get('name'), daemon=kwargs.get('daemon'))

        # 必要参数
        self.url = url
        self.method = method.upper() or 'GET'
        self.downloader = kwargs.get('downloader')
        if type(self.downloader).__name__ == 'type':
            raise TypeError(f'downloader must be a Downloader object, get {self.downloader.__name__} class')
        assert self.method in DEFAULT_METHOD_VALUE, f'Invalid method {method}'

        # 请求参数
        self.request_kwargs = {key: value for key, value in kwargs.items() if key in REQUEST_KEYS}
        if self.request_kwargs.get('data') or self.request_kwargs.get('json'): self.method = 'POST'

        # 自定义参数
        self.priority = kwargs.get('priority') or 0
        self.max_retry = kwargs.get('max_retry') or 0
        self.callback = kwargs.get('callback')
        self.failed_callback = self.downloader.pipeline.failed_pipeline
        self.error_callback = self.downloader.pipeline.error_pipeline
        self.retry_callback = self.downloader.pipeline.retry_pipeline
        self.session = kwargs.get('session')
        self.retry_count = 0
        self.is_start = False
        self.success = False
        self.error = False

        # 额外参数
        self.pocket = {}

        if args and not isinstance(args, tuple): args = (args,)
        self.func_args, self.func_kwargs = args_split(deepcopy(args) or ())
        self.request_kwargs = {'url': self.url, 'method': self.method, **self.request_kwargs}

    def run(self):
        self.is_start = True

        # 加载请求插件
        request = _load_extensions(target=self, extensions=self.downloader.request_extensions)
        self.__dict__.update(request.__dict__)

        start = time.time()
        try:
            if self.session:
                self.request_kwargs.pop('cookies', None)
                response = self.session.request(**self.request_kwargs)
            else:
                response = requests.request(**self.request_kwargs)

        except Exception as e:
            self.error = True
            if self.error_callback:
                self.error_callback(
                    self, e,
                    *self.func_args,
                    **{**self.func_kwargs,
                       'request_kwargs': self.request_kwargs}
                )
        else:
            if response.status_code != 200 and self.retry_count < self.max_retry:
                self.retry_count += 1
                time.sleep(self.retry_count * 0.1)

                if self.retry_callback:

                    request, *result = self.retry_callback(self, response, *self.func_args, **self.func_kwargs)
                    if request:
                        error_msg = 'Retry Error ... retry_pipeline must return request or response object'
                        if not isinstance(request, Request): raise TypeError(error_msg)
                        self.__dict__.update(request.__dict__)

                        if result:
                            resp = result[0]
                            if isinstance(resp, requests.Response): resp = Response(resp)
                            if not isinstance(resp, Response): raise TypeError(error_msg)
                            self._process_callback(resp, start)
                        else:
                            self.run()

            else:
                self._process_callback(response, start)

    def _process_callback(self, response, start):
        if response.status_code == 200: self.success = True

        response.cost_time = '{:.3f}'.format(time.time() - start)
        response.retry_times = self.retry_count
        response.request_kwargs = self.request_kwargs

        # 加载响应插件
        response = _load_extensions(target=response, extensions=self.downloader.response_extensions)

        if self.success:
            if self.callback:
                callback = self.callback
            else:
                callback = None
        else:
            if self.failed_callback:
                callback = self.failed_callback
            elif self.callback:
                callback = self.callback
            else:
                callback = None

        # 数据入口
        if callback:
            assert isinstance(self.downloader, Downloader)
            e_msg = 'Invalid yield value: {}, yield value must be Request or dict object'

            if not self.success and self.failed_callback:
                generator = callback(self, response, *self.func_args, **self.func_kwargs)
            else:
                generator = callback(response, *self.func_args, **self.func_kwargs)

            if isinstance(generator, Generator):
                for _ in generator:
                    if isinstance(_, Request):
                        self.downloader.push(_)
                    elif isinstance(_, dict):
                        self.downloader.push_item(_)
                    elif isinstance(_, tuple):
                        data, args, kwargs = self.downloader._process_callback_args(_)
                        if isinstance(data, dict):
                            self.downloader.push_item(_)
                        else:
                            raise TypeError(e_msg.format(_))
                    else:
                        raise TypeError(e_msg.format(_))

    def __repr__(self):
        return f'<{self.name} {self.__class__.__name__}> {self.method}:{self.url}, priority:{self.priority}'


class Downloader(object):
    __settings__ = ['wait_time', 'max_thread', 'extensions']

    def __init__(self, max_thread=None, wait_time=0, pipeline=None, end_callback=None, item_filter=None):
        self.thread_pool = PriorityQueue()
        self.item_pool = Queue()
        self.pipeline = pipeline
        self.end_callback = end_callback
        self.max_thread = max_thread or 10
        self.running_thread = Queue()
        self.count = {'Success': 0, 'Retry': 0, 'Failed': 0, 'Error': 0}
        self.wait_time = wait_time
        self.item_filter = item_filter
        self.close_countdown = 10
        self._close = False
        assert isinstance(item_filter, Iterable), 'item_filter must be a iterable object'

        # 插件
        self.request_extensions = []
        self.response_extensions = []

    def push(self, request):
        assert isinstance(request, Request), f'task must be a {Request.__name__} object.'
        self.thread_pool.push(request, request.priority)

    def push_item(self, item):
        self.item_pool.put(item)

    def _finish(self):
        finish = False
        for i in range(3):
            if self.thread_pool.empty() and self.running_thread.empty() and self.item_pool.empty():
                finish = True
            else:
                finish = False

        return finish

    @property
    def status(self):
        return 'Closed' if self._close else 'Running'

    def distribute_task(self):
        countdown = self.close_countdown
        while not self._close:
            if self.max_thread and self.running_thread.qsize() > self.max_thread:
                self._join_thread()
            else:
                request = self.thread_pool.pop()
                if request:
                    countdown = self.close_countdown
                    yield request
                elif not self._finish():
                    self._join_thread()
                else:
                    if countdown >= 0:
                        if countdown < self.close_countdown:
                            print('Wait task ...'.format(countdown + 1))
                        time.sleep(1)
                        countdown -= 1
                    else:
                        if self.end_callback: self.end_callback()
                        msg = f'All task is done. Success: {self.count.get("Success")}, Retry: {self.count.get("Retry")}, Failed: {self.count.get("Failed")}, Error: {self.count.get("Error")}'
                        print(msg)
                        self._close = True

            try:
                item = self.item_pool.get_nowait()
            except:
                pass
            else:
                yield item

    # 数据出口, 分发任务，数据，响应
    def start(self):
        for _ in self.distribute_task():
            try:
                if isinstance(_, Request):
                    self._start_request(_)
                elif isinstance(_, dict):
                    if self.item_filter: _ = {k: v for k, v in _.items() if k in self.item_filter}
                    self.pipeline.item_pipeline(_, *(), **{})
                elif isinstance(_, tuple):
                    data, args, kwargs = self._process_callback_args(_)
                    if isinstance(data, dict):
                        if self.item_filter: data = {k: v for k, v in data.items() if k in self.item_filter}
                        self.pipeline.item_pipeline(data, *args, **kwargs)
                    else:
                        raise TypeError(f'Invalid yield value: {_}')
                else:
                    raise TypeError(f'Invalid yield value: {_}')
            except Exception as e:
                print(e)

    @staticmethod
    def _process_callback_args(args):
        if isinstance(args, tuple):
            data = args[0]
            assert isinstance(data, (dict, Request, Response)), 'yield item, args, kwargs,  item be a dict'
            args, kwargs = args_split(args[1:])
            return data, args, kwargs
        else:
            raise TypeError(f'Invalid yield value: {args}')

    def _start_request(self, request):

        if request:
            time.sleep(self.wait_time + request.retry_count * 0.1)
            if not request.is_start: request.start()
            self.running_thread.put(request)

    def _join_thread(self):
        while not self.running_thread.empty():
            request = self.running_thread.get()
            request.join()
            if request.success:
                self.count['Success'] += 1
                self.count['Retry'] += request.retry_count
            elif request.error:
                self.count['Error'] += 1
            else:
                self.count['Failed'] += 1

    def __repr__(self):
        return '<Downloader> max_thread: {}, count: {}, wait_time: {}'.format(
            self.max_thread, self.count, self.wait_time
        )
