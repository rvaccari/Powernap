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


def require_permissions(func, permissions=None):
    def _formatter(*args, **kwargs):
        if permissions and not getattr(current_user, 'is_admin', False):
            # TODO: implement the actual permissions functionality.
            pass
            #if not current_user.has_permission("generic name", permissions):
            #    raise PermissionError(description={'permissions': permissions})
        return func(*args, **kwargs)
    return _formatter
