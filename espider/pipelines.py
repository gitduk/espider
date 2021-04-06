class BasePipeline(object):
    def process_item(self, item, *args, **kwargs):
        print(item)

    def close_pipeline(self):
        pass
