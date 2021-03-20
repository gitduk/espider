## data_factory

> 数据处理模块，主要是一些处理字典的函数



##### `search`

> 搜索字典中的键值对，如果有多个相同的键，值会被放到一个列表。



参数及其类型

- key : `str, list, tuple`

- data : `dict`



用法：

```python
data = {
    'name':'search',
    'intro':'search key/value in dict data',
    'desc':{
        'name':'find',
        'intro':'find something'
    }
}

print(search('name', data))
# output: ['search', 'find']

print(search(['name','intro'], data))
# output: {'name': ['search', 'find'], 'intro': ['search key/value in dict data', 'find something']}

```



##### `update`

>  更新字典中的键值对。



参数及其类型

- update_map : `dict`
- data : `dict`
- target_type : `str, tuple` 



用法：

```python
data = {
    'name':'search',
    'intro':'search key/value in dict data',
    'desc':{
        'name':'find',
        'intro':'find something'
    }
}

print(update({'name': 'PYTHON'}, data=data))
# output: {'name': 'PYTHON', 'intro': 'search key/value in dict data', 'desc': {'name': 'PYTHON', 'intro': 'find something'}}

print(update({'name': 'PYTHON'}, data=data, target_type=int))
# output: {'name': 'search', 'intro': 'search key/value in dict data', 'desc': {'name': 'find', 'intro': 'find something'}}
```



target_type 字段标明更新字段的类型，默认更新类型：`str, bytes, int, float, list, dict`，如果字典的值的类型不在更新类型范围内，则不更新值。



##### `replace`

> 替换字典中的键值对。



参数及其类型

- replace_map : `dict`
- data : `dict`
- replace_key : `bool`



用法：

```python
data = {
    'name':'search',
    'intro':'search key/value in dict data',
    'desc':{
        'name':'find',
        'intro':'find something'
    }
}

print(replace({'find': 'search'}, data=data))
# output: {'name': 'search', 'intro': 'search key/value in dict data', 'desc': {'name': 'search', 'intro': 'search something'}}

print(replace({'name': 'Name'}, data=data, replace_key=True))
# output: {'Name': 'search', 'intro': 'search key/value in dict data', 'desc': {'Name': 'find', 'intro': 'find something'}}
```



##### `strip`

> 清洗字典



参数及其类型

- *args : `str`
- data : `dict`
- strip_key : `bool`



用法：

```python
data = {
    'name':'search',
    'intro':'search key/value in dict data',
    'desc':{
        'name':'find',
        'intro':'find something'
    }
}

print(strip('key/', 'find', data=data))
# output: {'name': 'search', 'intro': 'search value in dict data', 'desc': {'name': '', 'intro': ' something'}}

print(strip('ame', data=data, strip_key=True))
# output: {'n': 'search', 'intro': 'search key/value in dict data', 'desc': {'n': 'find', 'intro': 'find something'}}
```



##### `delete`

> 删除键值对



参数及其类型

- *args : `str`
- data : `dict`
- target_type : `str, tuple`



用法：

```python
data = {
    'name':'search',
    'intro':'search key/value in dict data',
    'desc':{
        'name':'find',
        'intro':'find something'
    }
}

print(delete('desc', data=data))
# output: {'name': 'search', 'intro': 'search key/value in dict data'}
```



默认target_key 类型为 `str, bytes, int, float, list, dict`



##### `flatten`

> 展开字典



参数及其类型

- data : `dict`



用法：

```python
data = {
    'name':'search',
    'intro':'search key/value in dict data',
    'desc':{
        'Name':'find',
        'Intro':'find something'
    }
}
print(dict(flatten(data)))
# output: {'name': 'search', 'intro': 'search key/value in dict data', 'Name': 'find', 'Intro': 'find something'}
```



##### `merge`

> 合并字典



参数及其类型

- *args : `dict`
- overwrite : `bool`



用法：

```python
data1 = {
    'name':'search',
    'intro':'search key/value in dict data',
    'desc':{
        'Name':'find',
        'Intro':'find something'
    }
}

data2 = {
    'name':'find',
    'intro':'searching',
    'desc':{
        'Name':'search',
        'Intro':'find something'
    }
}

print(merge(data1, data2))
# output: {'name': ['search', 'find'], 'intro': ['search key/value in dict data', 'searching'], 'desc': {'Name': ['find', 'search'], 'Intro': ['find something', 'find something']}}

print(merge(data1, data2, overwrite=True))
# output: {'name': ['search', 'find'], 'intro': ['search key/value in dict data', 'searching'], 'desc': {'Name': ['find', 'search'], 'Intro': ['find something']}}
```



