from flask import request
from flask_login import current_user
from sqlalchemy import Column, Integer, String


class PermissionUserMixin(object):
    """Add to model that can be :class:`flask_login.current_user`.

    Inheriting classes should define `permissions_class` as the table that
    inherits from `PermissionsTableMixin`.
    """
    def has_permission(self):
        return self.permission_class.exists(**self.permission_kwargs)

    def add_permission(self):
        permission = self.permission_class(**self.permission_kwargs)
        permission.save()
        return permission

    @property
    def permission_kwargs(self):
        return {
            "user_id": current_user.id,
            "rule": request.url_rule,
            "method": request.method,
        }

    @property
    def redis_token(self):
        """Token stored in redis for ratelimiting and other datas."""
        return "{}:{}".format(str(self.__class__), self.id)



class PermissionTableMixin(object):
    __tablename__ = "powernap_mixins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer(), nullable=False, index=True)
    rule = Column(String(255), nullable=False)
    method = Column(String(8), nullable=False)
