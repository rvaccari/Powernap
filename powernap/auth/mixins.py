class PermissionsMixin(object):
    """Add to model that can be :class:`flask_login.current_user`."""
    @property
    def permissions(self):
        # TODO: handle the permissoins here
        return

    @permissions.setter
    def permissions(self, value):
        # TODO: handle the permissoins here
        return

    def has_permission(self, name, permissions):
        return (self.is_admin or self.permissions.get(name) in permissions)

    @property
    def redis_token(self):
        """Token stored in redis for ratelimiting and other datas."""
        return "{}:{}".format(str(self.__class__), self.id)
