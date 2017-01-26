from datetime import datetime

from sqlalchemy.sql.sqltypes import Boolean, Integer, String, DateTime

from powernap.exceptions import InvalidFormError
from core.ubersmithdb.types import Formatted, UnicodeSafe

query_columns = {}


class _QueryMeta(type):
    """On import makes `query_columns`.

    Key is column type defined by `impl` and value is string
    of the name of a :class:`.BaseQueryColumn` subclass."""
    def __init__(cls, name, bases, dct):
        impl = dct['impl']
        if not isinstance(impl, list):
            impl = [impl]
        for i in impl:
            query_columns[i] = name
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
    impl = [String, UnicodeSafe]


class DateTimeQueryColumn(BaseQueryColumn):
    impl = [DateTime]

    def handle(self, column, value, func):
        if isinstance(value, (int, str)):
            value = datetime.fromtimestamp(int(value))
        return super(DateTimeQueryColumn, self).handle(column, value, func)


class FormatedQueryColumn(BaseQueryColumn):
    ''' Allow querying based on strings for formatted int columns. '''
    impl = Formatted

    def _reverse_value_map_query(self, column, query_value):
        field = getattr(self.cls, column)
        value_map = field.property.columns[0].type.value_map
        for k, v in value_map.items():
            if v == query_value:
                return k
        else:
            error_message = (
                "'{query_value}' is not a valid parameter for '{column}'. "
                'Valid options are: {values}'
            ).format(
                query_value=query_value,
                column=column,
                values=', '.join(list(value_map.values()))
            )
            error = {'fields': {column: [error_message]}}
            raise InvalidFormError(description=error)

    def handle(self, column, value, func):
        self.check_exposed_column(column)
        if isinstance(value, str):
            value = self._reverse_value_map_query(column, value)
        return self.handle_method(column, value, func)
