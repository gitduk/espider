import redis
from w3lib.url import canonicalize_url
from espider.utils.tools import get_md5


class BaseMiddleware(object):

    def process_request(self, request, *args, **kwargs):
        pass

    def process_response(self, response, *args, **kwargs):
        pass

    def process_retry(self, request, response, *args, **kwargs):
        print('Retry: {}, {}'.format(request.url, response))
        return request

    def process_error(self, request, exception, *args, **kwargs):
        raise exception

    def process_failed(self, request, response, *args, **kwargs):
        pass

    def close_middleware(self):
        pass


class RequestFilter(BaseMiddleware):
    __REDIS_KEYS__ = [
        'db', 'password', 'socket_timeout',
        'socket_connect_timeout',
        'socket_keepalive', 'socket_keepalive_options',
        'connection_pool', 'unix_socket_path',
        'encoding', 'encoding_errors',
        'charset', 'errors',
        'decode_responses', 'retry_on_timeout',
        'ssl', 'ssl_keyfile', 'ssl_certfile',
        'ssl_cert_reqs', 'ssl_ca_certs',
        'ssl_check_hostname',
        'max_connections', 'single_connection_client',
        'health_check_interval', 'client_name', 'username'
    ]

    def __init__(self, host='localhost', port=6379, set_key=None, timeout=None, priority=None, **kwargs):
        self.redis_kwargs = {k: v for k, v in kwargs.items() if k in self.__REDIS_KEYS__}
        self.redis_db = redis.Redis(host=host, port=port, **self.redis_kwargs)

        self.set_key = set_key or 'urls'
        self.timeout = timeout
        self.priority = priority
        self.number = 0

    def process_request(self, request, *args, **kwargs):

        # 过滤层级
        if self.priority != request.priority: return request

        skey = self.set_key

        if self.timeout:
            if self.redis_db.exists(skey) and self.redis_db.ttl(skey) == -1:
                self.redis_db.expire(skey, self.timeout)

        kwargs = {
            'url': request.url,
            'method': request.method,
            'body': request.request_kwargs.get('data'),
            'json': request.request_kwargs.get('json')
        }
        code = self.redis_db.sadd(skey, self._fingerprint(request))
        if not code:
            print('<RequestFilter> Drop: {}'.format(kwargs))
            self.number += 1
            return 'drop'
        else:
            return request

    @staticmethod
    def _fingerprint(request):
        """
        request唯一表识
        @return:
        """
        url = request.url
        # url 归一化
        url = canonicalize_url(url)
        args = [url]

        for arg in ["params", "data", "files", "auth", "cert", "json"]:
            if request.request_kwargs.get(arg):
                args.append(request.requests_kwargs.get(arg))

        return get_md5(*args)

    def close_middleware(self):
        print('RequestFilter({}): Drop {} request'.format(self.priority, self.number))
