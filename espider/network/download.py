from espider.tools import PriorityQueue
from espider.network.request import RequestThread
import threading
from queue import Queue


class Downloader(object):
    def __init__(self, max_thread=None):
        self.thread_pool = PriorityQueue()
        self.max_thread = max_thread
        self.running_thread = Queue()
        self.download_number = 0

    def push(self, task):
        assert isinstance(task, RequestThread), f'task must be {type(RequestThread)}'
        self.thread_pool.push(task, task.priority)

    def start(self):
        while not self.thread_pool.empty():
            if self.max_thread:
                if threading.active_count() <= self.max_thread:
                    task = self.thread_pool.pop()
                    task.start()
                    self.download_number += 1
                else:
                    task = None
                    self._join_thread()
            else:
                task = self.thread_pool.pop()
                task.start()
                self.download_number += 1

            if task: self.running_thread.put(task)

        if not self.running_thread.empty():
            self._join_thread()

    def _join_thread(self):
        while not self.running_thread.empty():
            thread = self.running_thread.get()
            thread.join()
