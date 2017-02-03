import bleach
from flask import abort, current_app
from flask_login import current_user

from powernap.exceptions import PermissionError, UnauthorizedError


def public(func, public=False):
    def _formatter(*args, **kwargs):
        if not public and not getattr(current_user, 'is_admin', False):
            abort(503 if current_app.config["DEBUG"] else 404)
        return func(*args, **kwargs)
    return _formatter


def login(func, login=True):
    def _formatter(*args, **kwargs):
        if login and not current_user.is_authenticated():
            raise UnauthorizedError
        return func(*args, **kwargs)
    return _formatter


def needs_permission(func, needs_permission=False):
    def _formatter(*args, **kwargs):
        if needs_permission and not getattr(current_user, 'is_admin', False):
            if not current_user.has_permission():
                raise PermissionError(
                    description="You have not been granted permission.")
        return func(*args, **kwargs)
    return _formatter


def safe(func, safe=False):
    def _formatter(*args, **kwargs):
        res = func(*args, **kwargs)
        if not safe:
            clean = lambda res: res.set_data(bleach.clean(res.get_data()))
            if isinstance(res, (tuple)):
                clean(res[0])
            else:
                clean(res)
        return res
    return _formatter


def format_(func, format_=True):
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

        return ApiResponse(data, status_code, headers).response
    return _formatter
