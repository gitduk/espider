class BasePipeline(object):
    def retry_pipeline(self, request, response, *args, **kwargs):
        print(f'[{response.status_code}] Retry-{request.retry_count}: {request.request_kwargs}')
        return request

    def error_pipeline(self, request, exception, *args, **kwargs):
        raise exception

    def failed_pipeline(self, request, response, *args, **kwargs):
        print(f'Request Failed ... {response} Retry: {response.retry_times}\nargs: {args} kwargs: {kwargs}')

    def item_pipeline(self, item, *args, **kwargs):
        pass
