import os
import pymysql
from threading import RLock

lock = RLock()


class OpenCsv(object):
    def __init__(self, path, mode=None, delimiter=None):
        self.path = path
        self.mode = mode or 'a+'
        self.delimiter = delimiter or ','
        self.head = False
        self.file = None

    def __enter__(self):
        if os.path.exists(self.path):
            _file = open(self.path, 'r')
            head = _file.readline().strip('\n')
            self.head = None if not head else head.split(self.delimiter)
            _file.close()
        self.file = open(self.path, self.mode)
        return self

    def write_list_to_csv(self, data: list):
        if self.head:
            self.file.write(self.delimiter.join(str(v) for v in data) + '\n')
        else:
            self.head = [str(i) for i in range(1, len(data) + 1)]
            self.file.write(self.delimiter.join(self.head) + '\n')
            self.write_list_to_csv(data)

    def write_dict_to_csv(self, data: dict):
        if self.head:
            self.file.write(self.delimiter.join(str(v) for v in data.values()) + '\n')
        else:
            self.head = [str(k) for k in data.keys()]
            self.file.write(self.delimiter.join(self.head) + '\n')
            self.write_dict_to_csv(data)

    def read_all_to_dict(self, iter=True):
        lines = self.file.readlines()
        if iter:
            for line in lines[1:]:
                yield dict(zip(self.head, line.strip('\n').split(self.delimiter)))
        else:
            return [dict(zip(self.head, line.strip('\n').split(self.delimiter))) for line in lines[1:]]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file._close()


class Mysql(object):

    def __init__(self, host=None, user=None, password=None, database=None, port=None, charset='utf8mb4',
                 cursorclass=None, **kwargs):
        self.host = host or 'localhost'
        self.user = user or 'root'
        self.port = port or 3306
        self.cursorclass = cursorclass or pymysql.cursors.DictCursor
        self.password = password,
        self.database = database,
        self.port = port,
        self.charset = charset,
        self.kwargs = kwargs
        self.db = None
        self.cursor = None

    def connect(self):
        try:
            db = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                charset=self.charset,
                cursorclass=self.cursorclass,
                **self.kwargs
            )
            cursor = db.cursor()
        except Exception as e:
            print(e)
            return None, None
        else:
            self.db, self.cursor = db, cursor
            return self.db, self.cursor
