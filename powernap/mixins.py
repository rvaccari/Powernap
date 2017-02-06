import sqlalchemy
from flask import current_app
from flask.ext.sqlalchemy import BaseQuery
from flask_login import current_user

from powernap.exceptions import OwnerError
from powernap.helpers import model_attrs


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
        client_key, db_entry_key = model_attrs()
        current_user_id = getattr(current_user, client_key)
        instance_id = getattr(self, db_entry_key)
        is_owner = current_user_id == instance_id
        if not is_owner and throw:
            raise OwnerError
        return is_owner


class PowernapFormMixin(object):
    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

    def update_obj(self, obj=None, **kwargs):
        return self.commit(instance=(obj or self.instance), **kwargs)

    def create_obj(self, **kwargs):
        return self.commit(**kwargs)

    def save_obj(self, instance):
        instance.save()
        return instance

    def delete_obj(self, model=None, **kwargs):
        if model is None:
            model = self.model()
        self.data.update(**kwargs)
        cleaned = self._clean_data(self.data)
        for m in model.query.filter_by(**cleaned).all():
            m.delete()

    def commit(self, instance=None, **kwargs):
        if instance is None:
            instance = self.model()
        self.populate_obj(instance)
        for k, v in kwargs.items():
            setattr(instance, k, v)
        self.ensure_owner(instance)
        return self.save_obj(instance)

    def ensure_owner(self, instance):
        client_key, db_entry_key = model_attrs()
        if hasattr(instance, db_entry_key) and not current_user.is_admin:
            setattr(instance, db_entry_key, getattr(current_user, client_key))

    def format_errors(self):
        if not self.errors:
            return {}
        errors = {}
        generic_errors = self.errors.get('errors')
        if generic_errors:
            errors['errors'] = generic_errors
        errors['fields'] = {}
        for field, err in self.errors.items():
            if not field == 'errors':
                errors['fields'][field] = err
        return errors

    def add_error(self, error_message):
        self.errors.setdefault('errors', [])
        self.errors['errors'].append(error_message)

    def _clean_data(self, data):
        """Returns dict without keys that have u'' or None as values.

        The models should handle setting defaults not the form.
        """
        return {k: v for k, v in data.items()
                if not v == '' and v is not None}
