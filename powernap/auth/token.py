import hashlib
import os

from flask import current_app
from flask_login import current_user
from powernap.helpers import redis_connection


class TempToken(object):
    """Facilitate creating a temporary token hash to be stored in redis."""
    def __init__(self):
        self.redis = redis_connection()

    @staticmethod
    def keys():
        return [current_app.config["active_tokens_attr"]]

    @property
    def token_data(self):
        return {key: getattr(self, key) for key in TempToken.keys}

    @classmethod
    def create(cls, user):
        return cls(**{k: getattr(user, k) for k in TempToken.keys})

    @classmethod
    def retrieve(cls, token, redis=None):
        redis = redis if redis else redis_connection()
        data = redis.hgetall(token)
        temp_token = cls()
        for k in TempToken.keys:
            setattr(temp_token, k, getattr(data, k, None))
        return temp_token

    @staticmethod
    def delete(token):
        redis = redis_connection()
        redis.delete(token)
        key = active_tokens_key(current_user)
        redis.srem(key, token)

    def api_response(self):
        return self.token_data


def active_tokens_key(user):
    prefix = getattr(user, current_app.config["ACTIVE_TOKENS_PREFIX"], "active")
    attr_val = getattr(user, current_app.config["ACTIVE_TOKENS_ATTR"])
    return '{}:{}'.format(prefix, attr_val)


def make_hash(redis=None):
    """Return a random hash that does not exist as a token.

    :param redis: An active redis connection. If None creates its own
        connection.
    """
    redis = redis if redis else redis_connection()
    count = 0
    while count < 100:
        token = hashlib.sha1(os.urandom(64)).hexdigest()
        if not redis.get(token):
            return token
        count += 1
    raise Exception("Unable to generate unique hash.")


def create_temp_token(user, hash_func):
    """Create expiring auth token in redis. `config['TOKEN_EXPIRE']`."""
    redis = redis_connection()
    token = hash_func(redis)
    temp_token = TempToken.create(user)
    redis.hmset(token, temp_token.token_data())
    redis.sadd(active_tokens_key(user), token)
    redis.expire(token, current_app.config['TOKEN_EXPIRE'])
    return token


def request_user_wrapper(f):
    def inner(request):
        key = current_app.config.get("AUTH_HEADER", "X-Auth")
        return f(request.headers.get(key))
    return inner


def user_from_redis_token_wrapper(user_class):
    def user_from_redis_token(token, redis=None):
        redis = redis if redis else redis_connection()
        temp_token = TempToken.retrieve(token)
        pk = getattr(temp_token, current_app.config["active_tokens_attr"])
        return user_class.query.get(pk)
    return user_from_redis_token
