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

from sqlalchemy import func, inspect

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm.util import _ORMJoin

from powernap.exceptions import InvalidFormError


def raise_error(keys=[], args=[]):
    keys = [keys] if not isinstance(keys, list) else keys
    args = [args] if not isinstance(args, list) else args
    errors = {"query_construction": {'keys': keys, 'args': args}}
    raise InvalidFormError(description=errors)


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


def exclude(cls, query, column, value):
    mapper = inspect(cls)
    if not mapper.exclude_properties:
        mapper.exclude_properties = set()
    mapper.exclude_properties.add(column)
    return query


def order_by(cls, query, column, value):
    values = value.split(',')
    for value in values:
        modifier = "asc"
        if value.startswith('-'):
            modifier = "desc"
            value = value[1:]
        try:
            query = query.order_by(getattr(getattr(cls, value), modifier)())
        except AttributeError:
            raise_error(keys=value)
    return query


def not_eq(cls, query, column, value):
    """Not equals query."""
    return query.filter(getattr(cls, column) != value)


def icontains(cls, query, column, value):
    """Return icontains query."""
    return query.filter(
        func.LOWER(getattr(cls, column)).contains(value.lower())
    )


def inside(cls, query, column, value):
    """Return in_ query."""
    try:
        return query.filter(getattr(cls, column).in_(json.loads(value)))
    # Catching all exceptions is bad.  We'd like to catch
    # json.decoder.JSONDecodeError but doesn't exists below python3.5.
    except (TypeError, ValueError, Exception):
        return query


def not_inside(cls, query, column, value):
    """Return ~in_ query."""
    try:
        return query.filter(~getattr(cls, column).in_(json.loads(value)))
    # Catching all exceptions is bad.  We'd like to catch
    # json.decoder.JSONDecodeError but doesn't exists below python3.5.
    except (TypeError, ValueError, Exception):
        return query


def gt(cls, query, column, value):
    """Return > query."""
    return query.filter(getattr(cls, column) > value)


def gte(cls, query, column, value):
    """Return >= query."""
    return query.filter(getattr(cls, column) >= value)


def lt(cls, query, column, value):
    """Return < query."""
    return query.filter(getattr(cls, column) < value)


def lte(cls, query, column, value):
    """Return <= query."""
    return query.filter(getattr(cls, column) <= value)


def like(cls, query, column, value):
    """Return sql `like` query."""
    return query.filter(getattr(cls, column).like(value))


def max(cls, query, column, value):
    """Return sql `MAX` query."""
    return query.filter(func.max(getattr(cls, column)))


def min(cls, query, column, value):
    """Return sql `MIN` query."""
    return query.filter(func.min(getattr(cls, column)))
