from espider.spider import Spider
import time
import aiohttp
import asyncio


class Douban(Spider):
    __custom_setting__ = {
        'max_thread': 10
    }

    def start_requests(self, *args, **kwargs):
        for i in range(5):
            url = 'https://www.douban.com/doulist/45004834/?start={}&sort=time&playable=0&sub_type='.format(i * 25)
            yield self.request(url)

    def parse(self, response, *args, **kwargs):
        titles = response.xpath('//div[@class="title"]/a/text()').getall()
        for t in titles:
            print(t.strip())


start = time.time()
D = Douban()
D.run()
end = time.time()

print(end - start - 3)

loop = asyncio.get_event_loop()


async def main(url):
    # 获取 session 对象
    async with aiohttp.ClientSession() as session:
        # get 方式请求 httbin
        async with session.get(url) as response:
            print(response.status)
            print(await response.text())


tasks = []
for i in range(5):
    url = 'https://www.douban.com/doulist/45004834/?start={}&sort=time&playable=0&sub_type='.format(i * 25)
    tasks.append(main(url))

loop.run_until_complete(asyncio.wait(tasks))
loop.close()
