import redis


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
