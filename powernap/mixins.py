import sqlalchemy
from flask import current_app
from flask.ext.sqlalchemy import BaseQuery
from flask_login import current_user

from powernap.exceptions import OwnerError


class PowernapMixin(object):
    """
    Mixin that is required for any object that is returned throught the
    `format_` decorator.
    """
    query_class = BaseQuery
    exposed_fields = []

    def session(self):
        return self.query.session

    def delete(self):
        session = self.session()
        session.delete(self)
        session.commit()
        return True

    @classmethod
    def safe_delete(cls, pk):
        obj = cls.query.get_or_404(pk)
        obj.confirm_owner()
        obj.delete()
        return True

    def save(self):
        session = self.session()
        session.add(self)
        session.commit()
        return True

    @classmethod
    def exists(cls, **kwargs):
        exists = sqlalchemy.exists()
        for k, v in kwargs.items():
            exists = exists.where(getattr(cls, k) == v)
        try:
            return cls.query.with_entities(exists).scalar()
        except sqlalchemy.exc.ProgrammingError:
            return cls._slow_exists(kwargs)

    @classmethod
    def _slow_exists(cls, kwargs):
        try:
            return bool(cls.query.filter_by(**kwargs).count())
        except sqlalchemy.exc.InvalidRequestError:
            msg = "Exists query failed. cls: {}, kwargs: {}".format(cls, kwargs)
            raise RuntimeError(msg)

    @classmethod
    def get_or_create(cls, **kwargs):
        instance = cls.query.filter_by(**kwargs).first()
        if instance:
            return instance, False
        return cls.create(**kwargs), True

    @classmethod
    def create(cls, **kwargs):
        instance = cls(**kwargs)
        instance.save()
        return instance

    def confirm_owner(self, throw=True):
        client_key = current_app.config.get("ACTIVE_TOKENS_ATTR", "id")
        db_entry_key = current_app.config.get("DB_ENTRY_ATTR", "id")
        current_user_id = getattr(current_user, client_key)
        instance_id = getattr(self, db_entry_key)
        is_owner = current_user_id == instance_id
        if not is_owner and throw:
            raise OwnerError
        return is_owner
