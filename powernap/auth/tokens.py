import geo_ip
import hashlib
import os
from distutils.util import strtobool

from flask import current_app, request
from flask_login import current_user

from core import ubersmithdb
from core.mixins import CoreMixin
from core.extensions import db
from core.extensions import redis_connection
from core.helpers import (
    active_tokens_key,
    cache_as_attr,
    is_valid_ip,
    timestamp_now
)
from core.hvdb.models import AuthProfile
from core.ubersmithdb import Client, Contact, Admin
from core.ubersmithdb.types import UnicodeSafe


class ApiToken(CoreMixin, db.Model):
    """Permanent auth token."""
    __bind_key__ = 'api'
    __tablename__ = "token"

    exposed_fields = [
        'admin_id',
        'client_id',
        'contact_id',
        'name',
        'token',
    ]

    name = db.Column(UnicodeSafe(db.String(255)), nullable=False)
    client_id = db.Column(db.Integer)
    contact_id = db.Column(db.Integer)
    admin_id = db.Column(db.Integer)
    token = db.Column(db.String(50), nullable=False, primary_key=True)

    def api_response(self):
        info = {
            'name': self.name,
            'token': self.token,
            'client_id': self.client_id,
            'contact_id': self.contact_id,
        }
        if current_user.is_admin:
            info['admin_id'] = self.admin_id
        return info

    @property
    @cache_as_attr
    def user(self):
        if self.contact_id:
            return Contact.query.get(self.contact_id)
        elif self.admin_id:
            return Admin.query.get(self.admin_id)
        return Client.query.get(self.client_id)

    @staticmethod
    def create_from_user(name, user, token=None):
        """Take user and return hash of new :class:`.ApiToken`."""
        attr = "admin_id" if user.is_admin else "client_id"
        token = token if token else make_hash()
        token = ApiToken(name=name, token=token, **{attr: user.id})
        if user.is_contact:
            token.contact_id = user.id
        token.save()
        return token


class TempToken(object):
    """ This is not a db table. This class is to facilitate creating
    a temporary token hash to be stored in redis. """

    def __init__(self, *args, **kwargs):
        self.redis = redis_connection()
        for k, v in kwargs.items():
            setattr(self, k, v)

    def token_data(self):
        return {
            'request': self.request,
            'otp': self.otp,
            'client_id': self.client_id,
            'user_type': self.user_type,
            'user_id': self.user_id,
            'ip': self.ip,
            'created': self.created,
            'last_activity': self.last_activity,
            'username': self.username
        }

    @classmethod
    def create(cls, user, otp=False):
        return cls(
            request=1,
            otp=otp,
            client_id=user.client_id,
            user_type=user.user_type,
            user_id=user.id,
            ip=request.remote_addr,
            created=timestamp_now(),
            last_activity=timestamp_now(),
            username=user.login
        )

    @classmethod
    def retrieve(cls, token):
        temp_token = cls(token=token)
        temp_token.get_hash_from_redis()
        return temp_token

    @staticmethod
    def delete(token):
        redis = redis_connection()
        redis.delete(token)
        key = active_tokens_key(current_user)
        redis.srem(key, token)

    def get_hash_from_redis(self):
        token_hash = self.redis.hgetall(self.token)
        self.request = int(token_hash.get('request', 0))
        self.otp = strtobool(token_hash.get('otp', 'False'))
        self.client_id = int(token_hash.get('client_id', 0))
        self.user_id = int(token_hash.get('user_id', 0))
        self.user_type = token_hash.get('user_type')
        self.ip = token_hash.get('ip')
        self.username = token_hash.get('username')
        self.last_activity = int(token_hash.get('last_activity', 0))
        self.created = int(token_hash.get('created', 0))
        return token_hash

    def api_response(self):
        location = 'Unknown'
        ip = self.ip
        if is_valid_ip(ip):
            location = geo_ip.get_city_country(ip)
        data = self.token_data()
        data['location'] = location
        data['token'] = self.token.decode('utf-8')
        return data


def make_hash(redis=None):
    """Return a random hash that does not exist as a token.

    :param redis: An active redis connection. If None creates its own
        connection.

    Checks both permanent :class:`.ApiTokens` and tokens in redis.
    """
    if not redis:
        redis = redis_connection()
    count = 0
    while count < 100:
        token = hashlib.sha1(os.urandom(64)).hexdigest()
        is_api = ApiToken.exists(token=token)
        in_redis = redis.get(token)
        if not is_api and not in_redis:
            return token
        count += 1
    raise Exception("Unable to generate unique hash.")


def create_token(user, otp_pass=None):
    """Create expiring auth token in redis. `config['TOKEN EXPIRE']`."""
    redis = redis_connection()
    token = make_hash(redis)
    otp_valid = user.check_otp(otp_pass)
    temp_token = TempToken.create(user, otp=otp_valid)
    redis.hmset(token, temp_token.token_data())
    redis.sadd(active_tokens_key(user), token)
    redis.expire(token, current_app.config['TOKEN_EXPIRE'])
    return token


def user_from_request(request):
    token = request.headers.get('X-Auth')
    if token:
        user = user_from_token(token)
        if user:
            if not user.auth_profile and user.__class__ != Admin:
                AuthProfile.create_from_user(user)
            return user


def user_from_token(token):
    """Get user or None from token stored in redis or ApiToken."""
    return user_from_redis(token) or user_from_api_token(token)


def user_from_redis(token):
    redis = redis_connection()
    temp_token = TempToken.retrieve(token)
    user_type = temp_token.user_type
    user_id = temp_token.user_id
    if user_type and user_id:
        return getattr(ubersmithdb, user_type).query.get(user_id)


def user_from_api_token(token):
    api_token = ApiToken.query.filter_by(token=token).first()
    if api_token:
        return api_token.user
