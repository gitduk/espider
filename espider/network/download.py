import threading
from queue import Queue
from espider.utils.tools import PriorityQueue
from espider.network.request import RequestThread


class Downloader(object):
    def __init__(self, max_thread=None):
        self.thread_pool = PriorityQueue()
        self.max_thread = max_thread
        self.running_thread = Queue()
        self.download_number = 0
        self._extensions = []

    def push(self, request):
        assert isinstance(request, RequestThread), f'task must be {type(RequestThread)}'
        self.thread_pool.push(request, request.priority)

    def add_extension(self, extension, *args, **kwargs):
        if type(extension).__name__ == 'type':
            extension = extension()

        self._extensions.append(
            {
                'extension': extension,
                'args': args,
                'kwargs': kwargs,
                'count': 0
            }
        )

    def start(self):
        while not self.thread_pool.empty():
            if self.max_thread and threading.active_count() > self.max_thread:
                request = None
                self._join_thread()
            else:
                request = self.thread_pool.pop()

            if request:
                assert isinstance(request, RequestThread)

                if self._extensions:
                    for _ in self._extensions:
                        extension, args, kwargs = _.get('extension'), _.get('args'), _.get('kwargs')
                        if request:
                            if args and kwargs:
                                request = extension(request, *args, **kwargs)
                            elif args:
                                request = extension(request, *args)
                            elif kwargs:
                                request = extension(request, **kwargs)
                            else:
                                request = extension(request)

                            _['count'] += 1

                    assert isinstance(
                        request, RequestThread
                    ) or not request, 'Extensions must return RequestThread or None'

                if request:
                    if not request.is_alive(): request.start()
                    self.running_thread.put(request)
                    self.download_number += 1

        if not self.running_thread.empty():
            self._join_thread()

    def _join_thread(self):
        while not self.running_thread.empty():
            thread = self.running_thread.get()
            thread.join()
