import redis
from w3lib.url import canonicalize_url
from espider.utils.tools import get_md5


class BaseExtension(object):

    def process(self, target):
        pass


class RequestFilter(redis.client.Redis):
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

    def __init__(self, host='localhost', port=6379, set_key=None, timeout=None, **kwargs):
        self.redis_kwargs = {k: v for k, v in kwargs.items() if k in self.__REDIS_KEYS__}
        super().__init__(host=host, port=port, **self.redis_kwargs)

        self.set_key = set_key or 'urls'
        self.timeout = timeout
        self.priority = None

    def process(self, request, *args, **kwargs):

        # 过滤层级
        if self.priority != request.priority: return request

        skey = self.set_key

        if self.timeout:
            if self.exists(skey) and self.ttl(skey) == -1:
                self.expire(skey, self.timeout)

        kwargs = {
            'url': request.url,
            'method': request.method,
            'body': request.request_kwargs.get('data'),
            'json': request.request_kwargs.get('json')
        }
        code = self.sadd(skey, self._fingerprint(request))
        if not code:
            print('<RequestFilter> Drop: {}'.format(kwargs))
            return None
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


def _load_extensions(target, extensions):
    for extension_dict in extensions:
        extension, args, kwargs = extension_dict.get('extension'), extension_dict.get('args'), extension_dict.get(
            'kwargs')
        assert hasattr(extension, 'process'), 'extension must have process method'

        if args and kwargs:
            result = extension.process(target, *args, **kwargs)
        elif args:
            result = extension.process(target, *args)
        elif kwargs:
            result = extension.process(target, **kwargs)
        else:
            result = extension.process(target)

        if result: target = result

        if 'count' not in extension_dict.keys(): extension_dict['count'] = 0
        extension_dict['count'] += 1

    return target
