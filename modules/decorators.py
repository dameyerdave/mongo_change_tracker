from functools import wraps
from json import loads


def queryset_respose(f):
    @wraps(f)
    def func(*args, **kwargs):
        r = loads(f(*args, **kwargs).to_json())
        return r
    return func
