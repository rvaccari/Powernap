import bleach
from flask import abort, current_app
from flask_login import current_user

from powernap.exceptions import PermissionError, UnauthorizedError


def require_public(func, public=False):
    def _formatter(*args, **kwargs):
        if not public and not getattr(current_user, 'is_admin', False):
            abort(503 if current_app.config["DEBUG"] else 404)
        return func(*args, **kwargs)
    return _formatter


def require_login(func, login=True):
    def _formatter(*args, **kwargs):
        if login and not current_user.is_authenticated():
            raise UnauthorizedError
        return func(*args, **kwargs)
    return _formatter


def require_permission(func, needs_permission=False):
    def _formatter(*args, **kwargs):
        if needs_permission and not getattr(current_user, 'is_admin', False):
            if not current_user.has_permission():
                raise PermissionError(
                    description="You have not been granted permission.")
        return func(*args, **kwargs)
    return _formatter


def safe_response(func, safe=False):
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
