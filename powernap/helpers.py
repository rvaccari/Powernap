import importlib

from redis import Redis, ConnectionPool
from flask import current_app


class DecodedRedis(Redis):
    """Python 3.5 returns all items from redis as byte objects, decode them."""
    def execute_command(self, *args, **options):
        val = super(DecodedRedis, self).execute_command(*args, **options)
        return decode_object(val)


def decode_object(val):
    if isinstance(val, list):
        return list(map(lambda x: decode_value(x), val))
    elif isinstance(val, dict):
        return {decode_value(k): decode_value(v) for k, v in val.items()}
    else:
        return decode_value(val)


def decode_value(val):
    return val.decode('utf-8') if isinstance(val, bytes) else val


def redis_connection(db=None):
    settings = current_app.config['REDIS']
    if db is not None:
        settings['db'] = db
    pool = ConnectionPool(**settings)
    decode_bytes = current_app.config.get("DECODE_REDIS_BYTES", True)
    cls = DecodedRedis if decode_bytes else Redis
    return cls(connection_pool=pool, decode_responses=True)


def load_from_string(path):
    module, decorator_name = path.rsplit(".", 1)
    return getattr(importlib.import_module(module), decorator_name)
