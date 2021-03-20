import os


class OpenCsv(object):
    def __init__(self, path, delimiter=None, mode=None):
        self.path = path
        self.delimiter = delimiter or ','
        self.mode = mode or 'a+'
        self.head = False
        self.file = None

    def __enter__(self):
        if os.path.exists(self.path):
            _file = open(self.path, 'r')
            self.head = None if not _file.readline() else True
            _file.close()
        self.file = open(self.path, self.mode)
        return self

    def write_list_to_csv(self, data: list):
        line = [str(v) for v in data]
        self.file.write(self.delimiter.join(line) + '\n')

    def write_dict_to_csv(self, data: dict):
        if self.head:
            self.file.write(self.delimiter.join(str(k) for k in data.values()) + '\n')
        else:
            self.file.write(self.delimiter.join(str(k) for k in data.keys()) + '\n')
            self.head = True
            self.write_dict_to_csv(data)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()
