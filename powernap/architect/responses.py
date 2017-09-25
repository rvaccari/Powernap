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
    def default(self, o):

        if isinstance(o, Decimal):
            return float(o)
        elif hasattr(o, 'isoformat'):
            return o.isoformat()
        elif hasattr(o, 'api_response'):
            return o.api_response()
        try:
            return super(APIEncoder, self).default(o)
        except TypeError:
            msg = '{} is not json serilaizable. '.format(o)
            msg += 'Did you add an "api_response" method?'
            raise TypeError(msg)


class ApiResponse(object):
    """Create the base api_response."""
    status_code = 400
    results = None
    pagination = None

    def __init__(self, data, status_code, headers=None, json_encoder=None):
        """Make data json serializable, detect the status, and set success."""
        self.page = current_app.config['PAGINATION_PAGE']
        self.per_page = current_app.config['PAGINATION_PER_PAGE']
        self.status_code = status_code
        self.json_encoder = json_encoder or APIEncoder
        if self.status_code // 100 == 2:
            self.results = self.construct_results(data)
        else:
            self.results = data
            if getattr(current_user, 'is_admin', False) and self.status_code // 100 == 4:
                self.log_bad_request_from_admin(data)
        self.extra_headers = headers or {}

    def construct_results(self, results):
        """Format results to an acceptable format for json serializing.

        :param results: The data that will be converted to a serializable
            format.  Dictionaries, Booleans, Integers, Strings, Tuples, &
            other powernap datatypes are immediately returned.

            Both :class:`flask_sqlalchemy.Pagination` that contain db objs
            and lists that contain Lists that contain db objs are
            converted using :meth:`format_pagination_results` and
            :meth:`format_list_results` respectively.
        """
        if not results or isinstance(results, dict):
            pass
        elif isinstance(results, Pagination):
            results = self.format_pagination_results(results)
        elif isinstance(results, list):
            results = self.format_list_results(results)
        elif hasattr(results, 'api_response'):
            results = results.api_response()
        return results

    def format_pagination_results(self, results):
        """Format pagination results and set `self.pagination`."""
        self.pagination = self.get_pagination_params(results)
        return self.format_list_results(results.items)

    def format_list_results(self, results):
        """Run :meth:`api_response()` for each item that has the meth.

        Formats items with attr `api_response`. This does not convert
        lists to dicts. This can be a security vulnerability.

        Read more at: http://flask.pocoo.org/docs/0.10/security/#json-security.
        """
        formatted = []

        try:
            exclude_properties = list(session.exclude_properties)
        except AttributeError:
            exclude_properties = []

        for item in results:
            if hasattr(item, 'api_response'):
                try:
                    item = item.api_response(**{'exclude_properties': exclude_properties})
                except TypeError:
                    item = item.api_response()
            formatted.append(item)

        if exclude_properties:
            del session.exclude_properties

        return formatted

    def get_pagination_params(self, results):
        """Return pagination params from results."""
        formatted_data = {
            "current": results.page,
            'first': 1,
            'last': results.pages,
            'next': results.next_num,
            'per_page': results.per_page,
            'previous': results.prev_num,
            'total': results.total,
        }
        if results.next_num > results.pages:
            formatted_data['next'] -= 1
        return formatted_data

    @property
    def response(self):
        """Return jsonified response."""
        # Request id and rate limiting need to go in the header as well.
        # Make response type its own class so we can chage status codes.
        return self.make_response(self.results), self.status_code

    def make_response(self, results):
        """Make and return the json response."""
        if isinstance(results, dict):
            resp = jsonify(**{str(k): v for k, v in results.items()})
        else:
            results = json.dumps(results, cls=self.json_encoder)
            resp = Response(results, mimetype='application/json')
        headers = self.make_headers()
        resp.headers.extend(headers)
        return resp

    def make_headers(self):
        """Add additional headers to the response."""
        headers = self.make_pagination_headers()
        headers.update(self.extra_headers)
        return headers

    def make_pagination_headers(self):
        """Make link-headers for pagination."""
        return {'X-Pagination': self.pagination or {}}

    def log_bad_request_from_admin(self, data):
        """If not a 2XX response code, log bad requests made by an admin user.

        Admin users are almost always other applications.  Therefore, if a request
        if made that is expected to succeed but 4XX's that response needs to be
        logged for debugging.  This only works when the applications logging level
        is set to `logging.DEBUG`.  ex: `app.logger.setLevel(logging.DEBUG)`.
        """
        logging.warning("Bad Admin Request to '{}': {}".format(
            request.path, data))
