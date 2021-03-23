from collections.abc import Generator
from threading import Thread
from espider import settings
from espider.network import Request, Downloader, BaseSpider


class Spider(BaseSpider, Thread):
    __custom_setting__ = {}

    def __init__(self, *args, **kwargs):
        super(Spider, self).__init__(*args, **kwargs)
        super(BaseSpider, self).__init__()

        # 加载 setting
        for key, value in self.__class__.__custom_setting__.items():
            setattr(settings, key, value)

        self.downloader = Downloader()

    def start_requests(self):
        yield ...

    def run(self):
        if type(self.downloader).__name__ == 'type':
            self.downloader = self.downloader()

        if isinstance(self.start_requests, Generator):
            raise ValueError("函数 start_requests 必须是生成器: yield Request")

        for request in self.start_requests():
            if not isinstance(request, Request):
                raise ValueError("仅支持 yield Request")

            if not request.callback: request.callback = self.parse
            self.downloader.push(request)

        self.downloader.start()

    def parse(self, response, *args, **kwargs):
        pass
