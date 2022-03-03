import inspect
import asyncio
import enum
import time

from functools import wraps

CACHE = {}


def _get_cached_value(id_or_ids):
    if type(id_or_ids) is list:
        return [CACHE[_id] for _id in id_or_ids]
    return CACHE[id_or_ids]


def _wrap_and_store_coroutine(cache, key, coro):
    async def func():
        value = await coro
        cache[key] = value
        return value

    return func()


def _wrap_new_coroutine(value):
    async def new_coroutine():
        return value

    return new_coroutine()


class ExpiringCache(dict):
    def __init__(self, seconds):
        self.__ttl = seconds
        self.__timekeeper = {}
        super().__init__()

    def __verify_cache_integrity(self):
        # Have to do this in two steps...
        current_time = time.monotonic()
        to_remove = [
            k for k in self.keys() if current_time > (self.__timekeeper[k] + self.__ttl)
        ]
        for k in to_remove:
            del self[k]

    def __contains__(self, key):
        self.__verify_cache_integrity()
        return super().__contains__(key)

    def __getitem__(self, key):
        self.__verify_cache_integrity()
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        self.__timekeeper[key] = time.monotonic()
        super().__setitem__(key, value)


class Strategy(enum.Enum):
    timed = 1
    internal = 2
    raw = 3


def cache(strategy=Strategy.timed, ttl=3600):
    def decorator(func):
        if strategy is Strategy.timed:
            _internal_cache = ExpiringCache(ttl)
        elif strategy is Strategy.internal:
            _internal_cache = {}
        elif strategy is Strategy.raw:
            _internal_cache = CACHE

        def _make_key(args, kwargs):
            def _true_repr(o):
                # print("O", o)
                if o.__class__.__repr__ is object.__repr__:
                    print("ID", o.id)
                    return f"<{o.id}.{o.__class__.__module__}.{o.__class__.__name__}>"
                return repr(o)

            key = [f"{func.__module__}.{func.__name__}"]
            key.extend(_true_repr(o) for o in args)

            for k, v in kwargs.items():

                key.append(_true_repr(k))
                key.append(_true_repr(v))

            return ":".join(key)

        @wraps(func)
        def wrapper(*args, **kwargs):

            key = _make_key(args, kwargs)

            try:
                value = _internal_cache[key]
            except KeyError:
                value = func(*args, **kwargs)

                if inspect.isawaitable(value):
                    return _wrap_and_store_coroutine(_internal_cache, key, value)

                _internal_cache[key] = value
                return value
            else:
                if asyncio.iscoroutinefunction(func):
                    return _wrap_new_coroutine(value)
                return value

        def _invalidate(*args, **kwargs):
            try:
                del _internal_cache[_make_key(args, kwargs)]
            except KeyError:
                return False
            else:
                return True

        def _invalidate_containing(key):
            to_remove = []
            for k in _internal_cache.keys():
                if key in k:
                    to_remove.append(k)
            for k in to_remove:
                try:
                    del _internal_cache[k]
                except KeyError:
                    continue

        wrapper.cache = _internal_cache
        wrapper.get_key = lambda *args, **kwargs: _make_key(args, kwargs)
        wrapper.invalidate = _invalidate
        wrapper.invalidate_containing = _invalidate_containing
        return wrapper

    return decorator
