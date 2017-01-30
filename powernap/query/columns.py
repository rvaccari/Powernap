from datetime import datetime

from sqlalchemy.sql.sqltypes import Boolean, Integer, String, DateTime

from powernap.exceptions import InvalidFormError


QUERY_COLUMNS = {}


class _QueryMeta(type):
    """On import makes `QUERY_COLUMNS`.

    Key is column type defined by `impl` and value is string
    of the name of a :class:`.BaseQueryColumn` subclass."""
    def __init__(cls, name, bases, dct):
        impl = dct['impl']
        impl = [impl] if not isinstance(impl, list) else impl
        for i in impl:
            QUERY_COLUMNS[i] = cls
        super(_QueryMeta, cls).__init__(name, bases, dct)


class BaseQueryColumn(object, metaclass=_QueryMeta):
    """Handle query transforming for :class:`..transformer.QueryTransformer`.

    :attr impl: An object or list of objects who are sqla column types.
    :attr invalid: Names of invalid methods.  Will raise
        :class:`core.api.exceptions.InvalidFormError` if called.

    When :class:`..transformer.QueryTransformer` is choosing which Query
    Column to implement it chooses the one whos impl corresponds with
    the current `column` type.
    """
    impl = None
    invalid = []

    def __init__(self, cls, query):
        self.cls = cls
        self.query = query

    def check_exposed_column(self, column):
        if column and column not in self.cls.exposed_fields:
            errors = {'fields':{column: ["Invalid Argument: Field not exposed"]}}
            raise InvalidFormError(description=errors)
        return True

    def handle(self, column, value, func):
        """Updates the query based on the args."""
        self.check_exposed_column(column)
        return self.handle_method(column, value, func)

    def handle_method(self, column, value, func):
        """Updates query with `func` from :module:`core.mason.methods`."""
        from core.mason import methods
        func = func or "filter_by"
        if func in self.invalid:
            methods.raise_error(keys=func)
        return getattr(methods, func)(self.cls, self.query, column, value)


class IntegerQueryColumn(BaseQueryColumn):
    impl = Integer
    invalid = ['icontains']

    def filter_by(self, column, value):
        if value == 'True':
            value = True
        elif value == 'False':
            value = False
        return super(IntegerQueryColumn, self).filter_by(column, value)


class BooleanQueryColumn(IntegerQueryColumn):
    impl = Boolean
    invalid = ['icontains']


class StringQueryColumn(BaseQueryColumn):
    impl = String


class DateTimeQueryColumn(BaseQueryColumn):
    impl = [DateTime]

    def handle(self, column, value, func):
        if isinstance(value, (int, str)):
            value = datetime.fromtimestamp(int(value))
        return super(DateTimeQueryColumn, self).handle(column, value, func)
