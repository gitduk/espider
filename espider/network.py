import time
from collections.abc import Generator, Iterable
import threading
from queue import Queue
import urllib3
from espider.default import REQUEST_KEYS, DEFAULT_METHOD_VALUE
from espider.parser.response import Response
from espider.utils.tools import args_split, PriorityQueue, headers_to_dict, cookies_to_dict, json_to_dict
import espider.utils.requests as requests
from espider.middlewares import BaseMiddleware
from espider.pipelines import BasePipeline

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Request(threading.Thread):
    __settings__ = [
        'max_retry',
        'timeout'
    ]
    __DEFAULT_THREAD_VALUE__ = [
        'name',
        'daemon'
    ]

    def __init__(self, url, method='', **kwargs):
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
        self.session = kwargs.get('session')
        self.show_detail = kwargs.get('show_detail')
        self.retry_times = 0
        self.is_start = False
        self.success = False
        self.error = False

        # 额外参数
        self.pocket = {}

        cb_args = kwargs.get('cb_args')

        if isinstance(cb_args, list): cb_args = tuple(cb_args)
        if cb_args and not isinstance(cb_args, tuple): cb_args = (cb_args,)
        self.func_args = cb_args or ()
        self.func_kwargs = kwargs.get('cb_kwargs') or {}
        self.request_kwargs = {'url': self.url, 'method': self.method, **self.request_kwargs}

        # 加载 BaseMiddleware
        if not self.downloader.middlewares: self.downloader.add_middleware(BaseMiddleware)

    def run(self):
        if isinstance(self.request_kwargs.get('headers'), str):
            self.request_kwargs['headers'] = headers_to_dict(self.request_kwargs.get('headers'))
        if isinstance(self.request_kwargs.get('cookies'), str):
            self.request_kwargs['cookies'] = cookies_to_dict(self.request_kwargs.get('cookies'))
        if isinstance(self.request_kwargs.get('json'), str):
            self.request_kwargs['json'] = json_to_dict(self.request_kwargs.get('json'))

        self.is_start = True

        # 加载中间件
        request = _load_download_middleware(request=self, middlewares=self.downloader.middlewares)
        if request == 'DROP': return
        if request: self.__dict__.update(request.__dict__)

        start = time.time()
        try:
            if self.show_detail:
                print('{} Start request {} [{}] body: {} ...'.format(
                    self.name,
                    self.request_kwargs.get('url'),
                    self.method,
                    self.request_kwargs.get('body') or self.request_kwargs.get('json')))

            if self.session:
                self.request_kwargs.pop('cookies', None)
                response = self.session.request(**self.request_kwargs)
            else:
                response = requests.request(**self.request_kwargs)

            if self.show_detail:
                print('{} Downloaded request {} [{}] body: {}'.format(
                    self.name,
                    self.request_kwargs.get('url'),
                    self.method,
                    self.request_kwargs.get('body') or self.request_kwargs.get('json')))

        except Exception as e:
            self.error = True

            # 处理错误请求
            result = _load_error_middleware(self, middlewares=self.downloader.middlewares, exception=e)
            self._process_result(result, start)

        else:
            if response.status_code != 200 and self.retry_times < self.max_retry:
                self.retry_times += 1
                time.sleep(self.retry_times * 0.1)

                # 重新请求
                result = _load_retry_middleware(self, response, middlewares=self.downloader.middlewares)
                self._process_result(result, start)

            else:
                self._process_callback(response, start)

    def _process_result(self, result, start):
        if isinstance(result, Request):
            self.__dict__.update(result.__dict__)
            self.run()
        elif isinstance(result, Response):
            self._process_callback(result, start)

    def _process_callback(self, response, start):
        if response.status_code == 200: self.success = True

        response.cost_time = '{:.3f}'.format(time.time() - start)
        response.retry_times = self.retry_times

        # 加载中间件
        response_ = _load_download_middleware(
            response=response, middlewares=self.downloader.middlewares, args=self.func_args, kwargs=self.func_kwargs
        )
        if response_: response = response_

        if not self.success:  # 处理失败的请求
            result = _load_failed_middleware(self, response, middlewares=self.downloader.middlewares)

            # 当result为响应时，务必保证请求成功，否则陷入死循环
            if result:
                self._process_result(result, start)
                return

        # 数据入口
        if self.callback:
            assert isinstance(self.downloader, Downloader)

            result = self.callback(response, *self.func_args, **self.func_kwargs)

            if result:
                if isinstance(result, Generator):
                    e_msg = 'Invalid yield value: "{}", function {} must yield a Request or a dict object'
                    for _ in result:
                        if isinstance(_, Request):
                            self.downloader.push(_)
                        elif isinstance(_, dict):
                            self.downloader.push_item(_)
                        elif isinstance(_, tuple):
                            data, args, kwargs = _process_callback_args(_)
                            if isinstance(data, dict):
                                self.downloader.push_item(_)
                            else:
                                raise TypeError(e_msg.format(_, self.callback.__name__))
                        else:
                            raise TypeError(e_msg.format(_, self.callback.__name__))

                elif isinstance(result, Request):
                    self.downloader.push(result)
                elif isinstance(result, dict):
                    self.downloader.push_item(result)
                else:
                    raise TypeError('Invalid return value: {}, {} must return a Request or a dict object'.format(
                        result, self.callback.__name__
                    ))

    def __repr__(self):
        return f'<{self.name} {self.__class__.__name__} {self.method}:{self.url} priority:{self.priority}>'


class Downloader(object):
    __settings__ = ['wait_time', 'max_thread', 'close_countdown', 'distribute_time']

    def __init__(self, max_thread=None, wait_time=0, end_callback=None, **kwargs):
        self.thread_pool = PriorityQueue()
        self.item_pool = Queue()
        self.end_callback = end_callback
        self.max_thread = max_thread or 10
        self.running_thread = Queue()
        self.count = {'Success': 0, 'Retry': 0, 'Failed': 0, 'Error': 0}
        self.wait_time = wait_time
        self.item_filter = []
        self.close_countdown = kwargs.get('close_countdown') or 3
        self.distribute_item = kwargs.get('distribute_item') or True
        self._close = False
        assert isinstance(self.item_filter, Iterable), 'item_filter must be a iterable object'

        # 插件
        self._middlewares = []

        # 数据管道
        self._pipelines = []

        # debug
        self._debug = False

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
    def middlewares(self):
        return self._middlewares

    def add_middleware(self, middleware, index=0):
        if type(middleware).__name__ == 'type': middleware = middleware()
        middleware_ = {
            'middleware': middleware,
            'index': index
        }
        self._middlewares.append(middleware_)
        self._middlewares.sort(key=lambda x: x['index'])

    @property
    def pipeline(self):
        return self._pipelines

    def add_pipeline(self, pipeline, index=0):
        if type(pipeline).__name__ == 'type': pipeline = pipeline()

        if hasattr(pipeline, 'open_pipeline'): pipeline.open_pipeline()

        if not hasattr(pipeline, 'process_item'):
            raise AttributeError('Pipeline Object must have process_item method')

        pipeline_ = {
            'pipeline': pipeline,
            'index': index
        }
        self._pipelines.append(pipeline_)
        self._pipelines.sort(key=lambda x: x['index'])

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
                    elif not self._debug:
                        # 关闭管道
                        for pipeline in self._pipelines:
                            if hasattr(pipeline, 'close_pipeline'): pipeline.close_pipeline()

                        # 关闭中间件
                        for middleware in self._middlewares:
                            if hasattr(middleware, 'close_middleware'): middleware.close_middleware()

                        if self.end_callback: self.end_callback()
                        msg = f'All task is done. Success: {self.count.get("Success")}, Retry: {self.count.get("Retry")}, Failed: {self.count.get("Failed")}, Error: {self.count.get("Error")}'
                        print(msg)
                        self._close = True

            if self.distribute_item:
                try:
                    item = self.item_pool.get_nowait()
                except:
                    pass
                else:
                    yield item

    # 数据出口, 分发任务，数据，响应
    def start(self):
        for _ in self.distribute_task():
            if not _: continue
            try:
                if isinstance(_, Request):
                    # 开启线程
                    self._start_request(_)
                elif isinstance(_, dict):
                    if self.item_filter: _ = {k: v for k, v in _.items() if k in self.item_filter}

                    # 发送数据到数据管道
                    self._send_data(_)
                elif isinstance(_, tuple):
                    data, args, kwargs = _process_callback_args(_)
                    if isinstance(data, dict):
                        if self.item_filter: data = {k: v for k, v in data.items() if k in self.item_filter}
                        # 发送数据到数据管道
                        self._send_data(data, *args, **kwargs)
                    else:
                        raise TypeError(f'Invalid yield value: {_}')
                else:
                    raise TypeError(f'Invalid yield value: {_}')
            except Exception as e:
                print(e)

    def _send_data(self, data, *args, **kwargs):
        if not self._pipelines: self.add_pipeline(BasePipeline)
        for _pipeline in self._pipelines:
            result = _pipeline.get('pipeline').process_item(data, *args, **kwargs)
            if result: data = result

    def _start_request(self, request):

        if request:
            time.sleep(self.wait_time + request.retry_times * 0.1)
            if not request.is_start: request.start()
            self.running_thread.put(request)

    def _join_thread(self):
        while not self.running_thread.empty():
            request = self.running_thread.get()
            request.join()
            if request.success:
                self.count['Success'] += 1
                self.count['Retry'] += request.retry_times
            elif request.error:
                self.count['Error'] += 1
            else:
                self.count['Failed'] += 1

    def __repr__(self):
        return '<Downloader> max_thread: {}, count: {}, wait_time: {}'.format(
            self.max_thread, self.count, self.wait_time
        )


def _process_callback_args(args):
    assert isinstance(args[0], dict), 'yield item, args, kwargs,  item must be a dict'
    args_, kwargs = args_split(args[1:])
    return args[0], args_, kwargs


def _load_download_middleware(request=None, response=None, middlewares=None, args=None, kwargs=None):
    if not middlewares: return None

    middlewares_ = (_.get('middleware') for _ in middlewares)

    if request:
        for middleware in middlewares_:
            # 全局处理函数，每一个请求和响应都要经过
            if hasattr(middleware, 'process_request'):
                result = middleware.process_request(request, *request.func_args, **request.func_kwargs)
                if isinstance(result, str) and result.upper() == 'DROP': return result.upper()
                if result: request = result

        return request

    else:
        for middleware in middlewares_:
            # 全局处理函数，每一个请求和响应都要经过
            if hasattr(middleware, 'process_response'):
                result = middleware.process_response(response, *args, **kwargs)
                if result: response = result

        return response


def _load_retry_middleware(request, response, middlewares=None):
    if not middlewares: return None

    result = None
    for middleware_ in middlewares:
        middleware = middleware_.get('middleware')
        if hasattr(middleware, 'process_retry'):
            result = middleware.process_retry(request, response, *request.func_args, **request.func_kwargs)
            if isinstance(result, Request): request = result
            if isinstance(result, Response): response = result

    return result


def _load_error_middleware(request, middlewares=None, exception=None):
    if not middlewares: return None

    result = None
    for middleware_ in middlewares:
        middleware = middleware_.get('middleware')
        if hasattr(middleware, 'process_error'):
            result = middleware.process_error(request, exception, *request.func_args, **request.func_kwargs)
            if result: request = result

    return result


def _load_failed_middleware(request, response, middlewares=None):
    if not middlewares: return None

    result = None
    for middleware_ in middlewares:
        middleware = middleware_.get('middleware')
        if hasattr(middleware, 'process_failed'):
            result = middleware.process_failed(request, response, *request.func_args, **request.func_kwargs)
            if isinstance(result, Request): request = result
            if isinstance(result, Response): response = result

    return result
