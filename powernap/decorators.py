import json

import bleach
from flask import abort, current_app
from flask_login import current_user

from powernap.exceptions import PermissionError, UnauthorizedError


def public(func, public=False):
    """Identifies endpoints that are non-public and only available to admins."""
    def _formatter(*args, **kwargs):
        if not public and not getattr(current_user, 'is_admin', False):
            abort(503 if current_app.config["DEBUG"] else 404)
        return func(*args, **kwargs)
    return _formatter


def login(func, login=True):
    """Identifies public endpoints that do not require authenticated users."""
    def _formatter(*args, **kwargs):
        if login and not current_user.is_authenticated:
            raise UnauthorizedError
        return func(*args, **kwargs)
    return _formatter


def permission(func, permission=None):
    """Identifies endpoints that require the user to have permisssion."""
    def _formatter(*args, **kwargs):
        if permission and not getattr(current_user, 'is_admin', False):
            if not current_user.has_permission(permission):
                raise PermissionError(
                    description="You have not been granted permission.")
        return func(*args, **kwargs)
    return _formatter


def safe(func, safe=False):
    """Identifies endpoints that don't require sanitization of response data."""
    def _formatter(*args, **kwargs):
        res = func(*args, **kwargs)
        if not safe:
            def sanitize(data):
                """This function recursively bleaches all the data.

                This is not optimum, as we have to decode then recode.  This
                really should be done in the ApiResponse.  Need to rethink how
                decorators are registered for a route so that bleaching can be
                done before the response results are rendered.
                """
                if isinstance(data, dict):
                    data = {sanitize(k): sanitize(v) for k, v in data.items()}
                elif isinstance(data, (list, tuple)):
                    data = [sanitize(i) for i in data]
                elif isinstance(data, str):
                    data = bleach.clean(data)
                return data

            def clean(res):
                data = json.loads(res.get_data().decode())
                data = json.dumps(sanitize(data))
                res.set_data(data)

            if isinstance(res, (tuple)):
                clean(res[0])
            else:
                clean(res)
        return res
    return _formatter


def format_(func, format_=True, app=None):
    """Decorator to format return values into api responses.

    Functions with this decorator can do this:
        `return data, status_code`

    Where `data` is json serializable and `status_code` is an integer
    Both arguments are passed to the
    :class:`powernap.api.responses.ApiResponse` object before the final
    response is sent from Flask.
    """
    def _formatter(*args, **kwargs):
        from powernap.architect.responses import ApiResponse
        from powernap.auth.rate_limit import RateLimiter

        res = func(*args, **kwargs)
        if not format_:
            return res

        if isinstance(res, tuple):
            data, status_code = res
        elif isinstance(res, int):
            data = None
            status_code = res
        else:
            raise Exception("Invalid Response Type: {}".format(type(res)))

        rl = RateLimiter(current_user)
        headers = rl.headers()

        return ApiResponse(data, status_code, headers, app=app).response
    return _formatter
