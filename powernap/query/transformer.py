from collections import deque

from flask import current_app, request
from flask_login import current_user
from sqlalchemy import exc

from powernap.exceptions import InvalidFormError
from powernap.helpers import load_from_string
from powernap.query.columns import BaseQueryColumn, QUERY_COLUMNS


def construct_query(cls, enforce_owner=True, **kwargs):
    """Return :class:`flask_sqlalchemy.Pagination` object from kwargs.

    :param cls: Target SQLA model for query_construction.
    :param enforce_owner: Ensures `id` in the query is set to
        the `current_user`'s id.
    :param kwargs: Kwargs to overide the query_args passed to
        :meth:`.QueryTransformer.transform`.
    """
    query_args = get_query_args_for_cls(
        cls, enforce_owner=enforce_owner, **kwargs)
    return QueryTransformer(cls).transform(query_args)


def extend_query(query, enforce_owner=True, **kwargs):
    """Return :class:`flask_sqlalchemy.Pagination` object from kwargs.

    :param query: A query on an object.
    :param enforce_owner: Ensures `id` in the query is set to
        the `current_user`'s id.
    :param kwargs: Kwargs to overide the query_args passed to
        :meth:`.QueryTransformer.transform`.

    This method is for using `construct_query`like functionality to extend
    an existing query, like for objects that require complex queries to be
    constructed intitially.
    """
    cls = query._primary_entity.type
    query_args = get_query_args_for_cls(
        cls, enforce_owner=enforce_owner, **kwargs)
    return QueryTransformer(cls, query=query).transform(query_args)


def get_query_args_for_cls(cls, enforce_owner=True, **kwargs):
    """Get the queryargs from the request and override them where needed.

    :param kwargs: kwargs to override the query args with.
    :param enforce_owner: Ensures `id` in the query is set to
        the `current_user`'s id.

    This function serves as the primary means of ensuring query
    construction is done using only the current_user's id,
    and in cases of admin's to prevent confirm_owner from raising errors.
    """
    args = request.args.to_dict()
    args.update(kwargs)
    return override_owner_id(cls, args) if enforce_owner else args


def override_owner_id(cls, query_args):
    """Used to ensure that users cannot query other users data."""
    attr = current_app.config.get("ACTIVE_TOKENS_ATTR", "id")
    if not getattr(current_user, 'is_admin', False) and hasattr(cls, attr) and \
            hasattr(current_user, attr):
        query_args[attr] = getattr(current_user, attr)
    return query_args


class QueryTransformer:
    query_columns = QUERY_COLUMNS

    def __init__(self, cls=None, query=None):
        self.cls = cls or query._primary_entity.type
        self.initial_query = query
        self.page = current_app.config['PAGINATION_PAGE']
        self.per_page = current_app.config['PAGINATION_PER_PAGE']
        self.pagination = (self.page, self.per_page)

    def transform(self, query_args):
        """Return :class:`flask_sqlalchemy.Pagination` object from kwargs.

        :param query_args: A dictionary of values SQLA Alchemy will use to
            construct the query, where the key is the function/field name
            and the value is the value to pass to the function/field.
            It can contain 4 different types of items:

                1. Keys accepted by :meth:`db.session.query.filter_by`.

                    `kwargs = {'first': 'John', 'last': 'BeGood'}`
                    `self.cls.query.filter_by(first='John', last='BeGood')`

                2. Keys that are methods on `db.session.query`.

                (Theses keys must start with a `$` to designate they are
                not kwargs to pass to `filter_by`)

                    `kwargs = {'$order_by': 'first'}`
                    `self.cls.query.order_by('first')`

                3. Keys that require a definition of a special method.
                These methods are defined in :module:`..methods`.

                (Key must be in the format `column__method`.  These keys
                do not need `$` because the `__` identifies them as a
                non-field value.

                    `kwargs = {'subject__icontains': 'hello'}`
                    `..methods.icontains(*args)`

                4. Keys equal to `self.page` and `self.per_page`.

                (Theses keys must start with a `$` to designate they are
                not kwargs to pass to `filter_by`)

                    `kwargs = {'page': 2, 'per_page': 25}`
                    `self.cls.query.paginate(2, 25, False)`

        If a kwarg not passed to `filter_by` is invalid the exception is
        caught & the query continues executing.  If a kwarg not designated
        special, is not a pagination kwarg, & is an invalid field will raise
        a subclassed :class:`core.api.exceptions.ApiError`.
        """
        paginate = self.pop_pagination_kwargs(query_args)
        query = self.create_query(query_args)
        return self.paginate_query(query, paginate)

    def create_query(self, kwargs):
        """Create the query.  Called by :meth:`.QueryTransformer.transform`."""
        impl_data = self.prep_for_impl(kwargs)
        query = self.initial_query if self.initial_query else self.cls.query
        for value_tuple in impl_data:
            query = self.implement(query, value_tuple)
        return query

    def prep_for_impl(self, kwargs):
        """Return list of tuples for each column.

        Appends tuples for filter_by to the beggining of the list.
        The rest are appended in the order they are passed.

        NOTE: A priority system would be useful for the future.
        """
        impl_data = deque()
        for column, value in kwargs.items():
            method = 'appendleft'
            func = None
            if column.startswith('$') and not hasattr(self.cls, column[1:]):
                column = column[1:]
                method = 'append'
                if '__' in column:
                    column, func = column.split('__')
                else:
                    func = column
                    column = None
            getattr(impl_data, method)((column, value, func))
        return impl_data

    def implement(self, query, value_tuple):
        """Transform the query with column types corresponding query column."""
        column, value, func = value_tuple
        type_cls = None
        if column and hasattr(self.cls, column):
            try:
                # This fails when the attr is a property.
                type_cls = getattr(self.cls, column).type.__class__
            except AttributeError:
                type_cls = "PropertyQueryColumn"
            except exc.InvalidRequestError:
                pass
        impl_cls = self.query_columns.get(type_cls, BaseQueryColumn)
        return impl_cls(self.cls, query).handle(column, value, func)

    def pop_pagination_kwargs(self, kwargs):
        """Return popped kwargs of first items in `self.pagination` tuples.

        If :meth:`db.session.query.paginate` is passed just a `page`
        argument and `page > 1` the method will fail.  If a `per_page`
        argument is passed without a `page` the logical page number
        should be `1`.  Therefore if one of the kwargs is missing the
        `page` kwarg will default to `1`.
        """
        paginate = {}
        for key in self.pagination:
            key = '$' + key
            if key in kwargs:
                try:
                    paginate[key[1:]] = int(kwargs.pop(key))
                except TypeError:
                    pass
        if len(paginate) != len(self.pagination):
            paginate[self.page] = 1
        return paginate

    def paginate_query(self, query, paginate):
        """Return :class:`flask_sqlalchemy.Pagination` object from query."""
        try:
            return query.paginate(paginate.get(self.page, 1),
                                  paginate.get(self.per_page, query.count()),
                                  False)
        except exc.OperationalError as e:
            msg = "Invalid Value: {}".format(e.orig.args[-1])
            errors = {'query_construction': [msg]}
            raise InvalidFormError(description=errors)
