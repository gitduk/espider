class BasePipeline(object):

    def __init__(self, spider=None):
        self.spider = spider

    def open_pipeline(self):
        pass

    def process_item(self, item, *args, **kwargs):
        print(item)

    def close_pipeline(self):
        pass
