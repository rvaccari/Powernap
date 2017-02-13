from sqlalchemy import Column, Integer, String

from powernap.helpers import model_attrs


class PermissionUserMixin(object):
    """Add to model that can be :class:`flask_login.current_user`.

    Inheriting classes should define `permission_class` as the table that
    inherits from `PermissionsTableMixin`.
    """
    def has_permission(self, permission):
        client_key, _ = model_attrs()
        query = "{}%".format(permission)
        return bool(self.permission_class.query.filter(
            self.permission_class.permission.like(query),
            self.permission_class.user_id == getattr(self, client_key),
        ).first())

    def add_permission(self, permission):
        client_key, _ = model_attrs()
        permission, _ = self.permission_class.get_or_create(
            user_id=getattr(self, client_key),
            permission=permission,
        )
        return permission

    @property
    def permissions(self):
        client_key, _ = model_attrs()
        return self.permission_class.query.filter_by(
            user_id=getattr(self, client_key)).all()


class PermissionTableMixin(object):
    __tablename__ = "powernap_permissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer(), nullable=False, index=True)
    permission = Column(String(255), nullable=False)

    def api_response(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "permission": self.permission,
        }
