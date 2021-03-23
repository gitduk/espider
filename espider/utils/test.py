from espider.spider import Spider
from espider.network import Downloader


class TSpider(Spider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.downloader = Downloader()

        self.url = 'http://www.rufa.gov.cn/rufamain/check/queryPersonListByParam'
        self.json = '{\"pageNumber\":1,\"pageSize\":12,\"area\":[],\"areaCity\":[],\"serviceType\":[],\"disputeType\":[],\"name\":\"\",\"busyType\":\"organization_staff_type_lawyer\",\"cities\":[]}'

    def start_requests(self):
        for i in range(1, 10):
            self.update(pageNumber=i)
            yield self.request(args='test')

    def parse(self, response, *args, **kwargs):
        print(response)


if __name__ == '__main__':
    t = TSpider()
    t.start()
