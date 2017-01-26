import sqlalchemy
from flask import current_app
from flask.ext.sqlalchemy import BaseQuery
from flask_login import current_user
from sqlalchemy.orm.session import make_transient
from sqlalchemy.sql import func

from powernap.exceptions import OwnerError


class PowernapMixin(object):
    query_class = BaseQuery
    timestamp_fields = []
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

    def make_transient(self):
        """Disconnects the current instance from its row in the database.

        Useful for copying a instance quickly.
        Be sure to update the id field!
        Check out :meth:`next_primary_key`.
        """
        self.session().expunge(self)
        make_transient(self)

    @classmethod
    def next_primary_key(cls):
        return cls.query.session()(func.max(cls.id).label("id")).one().id

    def encode_byte_fields(self):
        for column in self.__table__.columns:
            if str(column.type).startswith("VARBINARY"):
                field = column.key
                val = getattr(self, field)
                if not isinstance(val, bytes):
                    setattr(self, field, str.encode(val))

    def confirm_owner(self, throw=True):
        key = current_app.config["ACTIVE_TOKENS_ATTR"]
        current_user_id = getattr(current_user, key)
        instance_id = getattr(self, key)
        is_owner = current_user_id != instance_id
        if not is_owner and throw:
            raise OwnerError
        return is_owner
