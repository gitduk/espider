import json

from espider.utils.tools import PriorityQueue
from espider.network.request import RequestThread
import threading
from espider.dbs.easy_redis import RequestFilter
from queue import Queue


class Downloader(object):
    def __init__(self, max_thread=None, request_filter=None):
        self.thread_pool = PriorityQueue()
        self.max_thread = max_thread
        self.running_thread = Queue()
        self.download_number = 0
        self.request_filter = request_filter

    def push(self, task):
        assert isinstance(task, RequestThread), f'task must be {type(RequestThread)}'
        self.thread_pool.push(task, task.priority)

    def start(self):
        while not self.thread_pool.empty():
            if self.max_thread and threading.active_count() > self.max_thread:
                task = None
                self._join_thread()
            else:
                task = self.thread_pool.pop()

            if task and self._filter_task(task):
                task.start()
                self.running_thread.put(task)
                self.download_number += 1

        if not self.running_thread.empty():
            self._join_thread()

    def _filter_task(self, task):
        if self.request_filter:
            assert isinstance(self.request_filter, RequestFilter)
            skey = self.request_filter.set_key

            if self.request_filter.timeout:
                if self.request_filter.exists(skey) and self.request_filter.ttl(skey) == -1:
                    self.request_filter.expire(skey, self.request_filter.timeout)

            kwargs = {
                'url': task.url,
                'method': task.method,
                'body': task.request_kwargs.get('data'),
                'json': task.request_kwargs.get('json')
            }
            code = self.request_filter.sadd(skey, json.dumps(kwargs))
            if not code:
                print(f'<RequestFilter Drop>: {json.dumps(kwargs)}')

            return code
        else:
            return True

    def _join_thread(self):
        while not self.running_thread.empty():
            thread = self.running_thread.get()
            thread.join()
