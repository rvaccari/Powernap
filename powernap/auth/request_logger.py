import json
from datetime import datetime, timedelta
from flask import current_app, request
from flask_login import current_user
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from core.extensions import db, celery
from core.helpers import api_url_prefix
from core.mixins import CoreMixin
from core.ubersmithdb.models import Admin, Client, Contact
from core.settings import SENSITIVE_ENDPOINTS


def log_request(res):
    log_args = {}
    log_args.update(_parse_response(res))
    log_args.update(_parse_request())
    log_args.update(_parse_user())
    log_request_task.delay(log_args)
    return res


@celery.task(name='request_logger.log_request')
def log_request_task(log_args):
    log = RequestLogEntry(**log_args)
    log.save()
    _publish_to_socket(log)


def _parse_user():
    user = current_user
    return {
        'anonymous': user.is_anonymous(),
        'client_id': getattr(user, 'client_id', None),
        'user_id': getattr(user, 'id', None),
        'user_type': getattr(user, 'user_type', None)
    }


def _redact_sensitive_data(body, attrs):
    try:
        body = json.loads(body)
    except ValueError:
        return body
    for attr in attrs:
        body.pop(attr, None)
    return json.dumps(body)


def _get_request_body():
    req_body = request.get_data().decode('utf-8')
    if request.method not in ['PUT', 'POST']:
        return req_body
    path = request.path.lstrip(api_url_prefix())
    attrs_to_strip = SENSITIVE_ENDPOINTS.get(path)
    if attrs_to_strip:
        return _redact_sensitive_data(req_body, attrs_to_strip)
    return req_body


def _parse_request():
    req_body = _get_request_body()
    return {
        'url': request.url,
        'request_body': req_body,
        'request_method': request.method
    }


def _parse_response(res):
    try:
        res_data = res.get_data().decode('utf-8')
    except UnicodeDecodeError:
        res_data = 'COULD NOT DECODE BYTE STRING RESPONSE TO UTF-8'
    return {
        'response_body': res_data,
        'status_code': res.status_code
    }


def _publish_to_socket(log):
    '''TODO: publish to websocket channel.'''
    pass


def purge_old_logs(**kwargs):
    days_ago = kwargs.get('days_ago', current_app.config['ACTIVITY_LOG_EXPIRATION'])
    expiration_date = datetime.utcnow() - timedelta(days=days_ago)
    RequestLogEntry.query.filter(RequestLogEntry.created < expiration_date).delete()


class RequestLogEntry(CoreMixin, db.Model):
    __bind_key__ = 'hvdb'

    exposed_fields = [
        'id',
        'client_id',
        'created',
        'url',
        'user_id',
        'user_type',
        'request_body',
        'request_method',
        'response_body',
        'status_code'
    ]

    id = Column(Integer, primary_key=True)
    anonymous = Column(Boolean, nullable=False, default=1)
    client_id = Column(Integer, index=True)
    created = Column(DateTime, default=datetime.utcnow, index=True)
    url = Column(String(255), nullable=False)
    user_id = Column(Integer, index=True)
    user_type = Column(String(10), nullable=False, default='Anonymous')
    request_body = Column(Text)
    request_method = Column(String(10), nullable=False)
    response_body = Column(Text)
    status_code = Column(SmallInteger, nullable=False)

    @property
    def client(self):
        return Client.query.get(self.client_id)

    @staticmethod
    def user_from_type(user_type, user_id):
        models = {
            "client": Client,
            "contact": Contact,
            "admin": Admin
        }
        return models[user_type.lower()].query.get(user_id)

    @property
    def user(self):
        return self.user_from_type(self.user_type, self.user_id)

    def api_response(self):
        return {
            'id': self.id,
            'anonymous': self.anonymous,
            'client_id': self.client_id,
            'created': self.created,
            'url': self.url,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'request_body': self.request_body,
            'request_method': self.request_method,
            'response_body': self.response_body,
            'status_code': self.status_code
        }
