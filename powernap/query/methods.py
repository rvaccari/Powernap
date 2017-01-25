"""
Contains methods for :meth:`core.mason.columns.BaseQueryColumn.handle_special`.

Add a new method below whose name corresponds with the `func`
argument (which ultimately comes from `request.args`.) that
is passed to `handle_special`.

For example if you wanted to do the sqla query:

    `column__max`

You would define the method:

    `def max(cls, query, column, value):
        return query(func.max(column))
"""
import json

from sqlalchemy import func
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm.util import _ORMJoin

from core.api.exceptions import InvalidFormError
from core.ubersmithdb.types import Formatted


def convert_formatted(f):
    """Catches values that are invalid db values but have value_map equivelants.

    The :class:`Formatted` and :class:`Modelled` have `value_map` attrs that
    normalize db values that are not human readable to values that are.
    Like the Integer column status would take and receive "active" instead of 1.
    This decorator, ensures that if a non-humanreadable value is passed, we
    convert it to the available human readable value if it is available.
    """
    def inner(cls, query, column, value):
        col = getattr(cls, column or '', None)

        def convert_value(value, no_conversion=True):
            value_type = col.property.columns[0].type
            # Not all value_type's have value_map attr
            if not hasattr(value_type, 'value_map'):
                try:
                    return value_type.python_type(value)
                except ValueError:
                    raise RuntimeError('Not a valid field value. Expected int.')

            value_map = value_type.value_map
            if value in value_map.values():
                return value
            elif value in value_map:
                return value_map[value]
            elif no_conversion:
                try:
                    value = col.type.impl.python_type(value)
                except ValueError:
                    pass
            raise RuntimeError('Not a valid field value.')

        col_exists = col is not None
        has_type = hasattr(col, 'type')
        if col_exists and has_type and col.type.__class__ == Formatted:
            try:
                value = convert_value(value)
            except RuntimeError:
                return query
        return f(cls, query, column, value)
    return inner


def raise_error(keys=[], args=[]):
    keys = [keys] if not isinstance(keys, list) else keys
    args = [args] if not isinstance(args, list) else args
    errors = {"query_construction": {'keys': keys, 'args': args}}
    raise InvalidFormError(description=errors)


@convert_formatted
def filter_by(cls, query, column, value):
    """Do sqlalchemy filtering on the query.

    Joined queries will filter_by the joined table.  We want to filter
    by the original table as the joined table can be filtered before
    it is passed to :meth`extend_query`.  So use :meth:`filter` for
    joined queries.
    """
    try:
        if query._from_obj and query._from_obj[0].__class__ == _ORMJoin:
            return query.filter(getattr(cls, column) == value)
        else:
            return query.filter_by(**{column: value})
    except InvalidRequestError as e:
        bad_arg = e
        if hasattr(e, 'message'):
            bad_arg = e.message.split("'")[-2]
        raise_error(keys=bad_arg)


@convert_formatted
def order_by(cls, query, column, value):
    modifier = "asc"
    if value.startswith('-'):
        modifier = "desc"
        value = value[1:]
    try:
        return query.order_by(getattr(getattr(cls, value), modifier)())
    except AttributeError:
        raise_error(keys=value)


@convert_formatted
def not_eq(cls, query, column, value):
    """Not equals query."""
    return query.filter(getattr(cls, column) != value)


@convert_formatted
def icontains(cls, query, column, value):
    """Return icontains query."""
    return query.filter(
        func.LOWER(getattr(cls, column)).contains(value.lower())
    )


@convert_formatted
def inside(cls, query, column, value):
    """Return in_ query."""
    try:
        return query.filter(getattr(cls, column).in_(json.loads(value)))
    # Catching all exceptions is bad.  We'd like to catch
    # json.decoder.JSONDecodeError but doesn't exists below python3.5.
    except (TypeError, ValueError, Exception):
        return query


@convert_formatted
def not_inside(cls, query, column, value):
    """Return ~in_ query."""
    try:
        return query.filter(~getattr(cls, column).in_(json.loads(value)))
    # Catching all exceptions is bad.  We'd like to catch
    # json.decoder.JSONDecodeError but doesn't exists below python3.5.
    except (TypeError, ValueError, Exception):
        return query


@convert_formatted
def gt(cls, query, column, value):
    """Return > query."""
    return query.filter(getattr(cls, column) > value)


@convert_formatted
def gte(cls, query, column, value):
    """Return >= query."""
    return query.filter(getattr(cls, column) >= value)


@convert_formatted
def lt(cls, query, column, value):
    """Return < query."""
    return query.filter(getattr(cls, column) < value)


@convert_formatted
def lte(cls, query, column, value):
    """Return <= query."""
    return query.filter(getattr(cls, column) <= value)


@convert_formatted
def like(cls, query, column, value):
    """Return sql `like` query."""
    return query.filter(getattr(cls, column).like(value))
