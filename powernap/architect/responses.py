import logging
import json
import re
from decimal import Decimal

from sqlalchemy import inspect
from flask import current_app, jsonify, Response, request, session
from flask_login import current_user
from flask_sqlalchemy import Pagination


class APIEncoder(json.JSONEncoder):
    """Allows json.dumps to accept classses with api_respones method."""
    def __init__(self, exclude_properties=None, *args, **kwargs):
        self.exclude_properties = exclude_properties or []
        return super(APIEncoder, self).__init__(*args, **kwargs)

    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        elif hasattr(o, 'isoformat'):
            return o.isoformat()
        elif hasattr(o, 'api_response'):
            return self.get_api_response(o)
        try:
            return super(APIEncoder, self).default(o)
        except TypeError:
            msg = '{} is not json serilaizable. '.format(o)
            msg += 'Did you add an "api_response" method?'
            raise TypeError(msg)

    def get_api_response(self, item):
        try:
            item = item.api_response(**{'exclude_properties': self.exclude_properties})
        except TypeError:
            item = item.api_response()
        return item


class ApiResponse(object):
    """Create the base api_response."""
    def __init__(self, data, status_code, headers=None, json_encoder=APIEncoder):
        self.data = data
        self.headers = headers or {}
        self.status_code = status_code
        self.headers = headers or {}
        self.json_encoder = self.prepped_encoder(json_encoder)
        if isinstance(data, Pagination):
            self.headers.update({'X-Pagination': self.pagination_headers(data)})
            self.data = data.items

    def prepped_encoder(self, json_encoder):
        """Allows for a APIEncoder initialized with the excluded props."""
        exclude_properties = getattr(session, 'exclude_properties', [])
        if exclude_properties:
            del session.exclude_properties
        return lambda *args, **kwargs: json_encoder(exclude_properties, *args, **kwargs)

    def pagination_headers(self, data):
        return {
            "current": data.page,
            'first': 1,
            'last': data.pages,
            'next': data.pages if data.next_num > data.pages else data.next_num,
            'per_page': data.per_page,
            'previous': data.prev_num,
            'total': data.total,
        }

    @property
    def response(self):
        data = json.dumps(self.data, cls=self.json_encoder)
        resp = Response(data, mimetype='application/json')
        resp.headers.extend(self.headers)
        
        self.log_error_if_bad_admin_request(data)
        return resp, self.status_code

    def log_error_if_bad_admin_request(self, data):
        if not current_app.config['DEBUG'] and \
                getattr(current_user, 'is_admin', False) and \
                status_code // 100 == 4:
            msg = "Bad Admin Request to '{}': {}".format(request.path, data)
            logging.warning(msg)

