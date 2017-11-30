import inspect
from copy import deepcopy

from flask import Blueprint, current_app, request
from flask_graphql import GraphQLView
from flask_login import LoginManager

from powernap.architect.loaders import init_view_modules
from powernap.auth.rate_limit import check_rate_limit
from powernap.auth.token import (
    user_from_redis_token_wrapper,
    request_user_wrapper,
)
from powernap.cors import init_cors
from powernap.decorators import format_
from powernap.exceptions import ApiError
from powernap.helpers import load_from_string
from powernap.http_codes import (
    empty_success_code,
    error_code,
    post_success_code,
    success_code,
)
from powernap.query.transformer import construct_query


@format_
def api_error(e):
    """Error handler that returns error dict with error msg."""
    desc = e.description
    if isinstance(desc, dict):
        content = desc
    else:
        content = {"errors": [desc]}
    return content, e.code


class Architect:
    """Registers multiple ResponseBlueprints and initializes settings."""
    def __init__(
        self, version=1, name="architect", prefix=None, base_dir="",
        template_dir="", crudify_funcs={}, user_class="", user_loader="",
        login_manager="flask_login.LoginManager",
        decorators=[
            "powernap.decorators.format_",
            "powernap.decorators.safe",
            "core.otp.decorators.otp",
            "powernap.decorators.permission",
            "powernap.decorators.login",
            "powernap.decorators.public",
        ],
        response_blueprint="powernap.architect.blueprints.ResponseBlueprint",
        request_class="powernap.architect.requests.ApiRequest",
        api_encoder="powernap.architect.responses.APIEncoder",
        before_request_funcs=["powernap.auth.rate_limit.check_rate_limit"],
        after_request_funcs=[], permissions=None, graphql_session_func=None):
        """
        :param version: (int): version number for endpoints registerd with this
            architect.
        :param name: (string): a name for this architect
        :param prefix: (string): a url prefix to append to all endpoints.
            Requires '{}' to format in the version number. If not provided
            `current_app.config["API_URL_PREFIX"] will be used.
        :param decorators: (list): List of strings containing paths to
            functions that will decorate every route.
        :param base_dir: (string): the full path of the base directory of the
            Flask application.
        :param template_dir: (string) the full path of the template directory
        :param crudify_funcs: (dict): keys are crudify request types keys
            are functions that are used for crudifying.
        :param user_class: (string): Path to class that `user_from_redis_token`
            should return an instance of for the `current_user`.
        :param user_loader: (string): Path to function for
            `login_manager.set_loader`.
        :param login_manager: (string): Path to class used to used to set
            current_user value.
        :param response_blueprint: (string): import string for class used for
            flask blueprints.  Must inherit from `ResponseBlueprint`.
        :param request_class: (strign): Import string for class used for
            requests.
        :param api_encoder: (string): Path to Json encoder to be used by the
            application.
        :param before_request_funcs: (list): List of function paths to run
            before requests.
        :param after_request_funcs: (list): List of function paths to run
            after requests.
        :param permissions: (dict): Dictionary where keys are permission strings
            and values are human readable equivalents. Permissions strings
            are . seperated values.  e.g. "device" or "device.edit".  Perms are
            recursive. Any user with the "device.edit" permission would also
            have the "device" permission.
        :param graphql_session_func: (string): Path to Func when executed
            returns a SqlAlchemy session to be used with graphql views.
        """
        self.blueprints = []
        self.version = version
        self.name = name
        self._prefix = prefix
        self.base_dir = base_dir
        self.template_dir = template_dir
        self.crudify_funcs = {
            k: crudify_funcs.get(k)
            for k in ("GET", "GET ONE", "PUT", "POST", "DELETE")
        }
        self._init_login_manager(login_manager, user_loader, user_class)
        self.decorators = [load_from_string(path) for path in decorators]
        self.response_blueprint = load_from_string(response_blueprint)
        self.request_class = load_from_string(request_class)
        self.api_encoder = load_from_string(api_encoder)
        self.before_request_funcs = [load_from_string(path)
                                    for path in before_request_funcs]
        self.after_request_funcs = [load_from_string(path)
                                    for path in after_request_funcs]
        self.permissions = permissions or []
        self.graphql_session_func = load_from_string(graphql_session_func)

    def _init_login_manager(self, login_manager, user_loader, user_class):
        """Loads the flask_login manager with the user retrieval function."""
        if not user_loader and not user_class:
            raise Exception(
                'Define either the "user_loader" or "user_class" kwarg.')
        user_class = load_from_string(user_class) if user_class else None
        user_loader = load_from_string(user_loader) if user_loader else None
        user_loader = user_loader or user_from_redis_token_wrapper(user_class)
        self.login_manager = load_from_string(login_manager)()
        self.login_manager.request_loader(request_user_wrapper(user_loader))

    def init_app(self, app):
        with app.app_context():
            app.json_encoder = self.api_encoder
            self.login_manager.init_app(app)
            app.register_blueprint(self)
            app.request_class = self.request_class
            app.register_error_handler(ApiError, api_error)
            app.register_error_handler(404, api_error)
            init_cors(app)

    @property
    def prefix(self):
        """Full prefix (including version number) passed to sub blueprint."""
        prefix = self._prefix or current_app.config["API_URL_PREFIX"]
        return prefix.format(version=self.version)

    @property
    def decorator_names(self):
        """Names of decorators applied to sub blueprint routes."""
        return [decorator.__name__ for decorator in self.decorators]

    def sub_blueprint(self, name, url_prefix='', **kwargs):
        """Create a new Blueprint for the Architect to register.

        Should only be invoked in the top of files named `views.py`.
        """
        default_options = {k: kwargs.pop(k) for k in self.decorator_names
                           if k in kwargs}
        defaults = {
            'url_prefix': "{}{}".format(self.prefix, url_prefix),
            'template_folder': self.template_dir,
            "crudify_funcs": self.crudify_funcs,
            "graphql_session_func": self.graphql_session_func,
        }
        for k, v in defaults.items():
            if k not in kwargs:
                kwargs[k] = v

        blueprint = self.response_blueprint(
            name, self.decorators, default_options=default_options,
            permissions=self.permissions, **kwargs)
        for func in self.before_request_funcs:
            blueprint.before_request(func)
        for func in self.after_request_funcs:
            blueprint.after_request(func)
        self.blueprints.append(blueprint)
        return blueprint

    def register(self, app, options, first_registration):
        """Register all the sub blueprints with the app."""
        init_view_modules(self.base_dir)
        for blueprint in self.blueprints:
            app.register_blueprint(blueprint, **options)

    @property
    def jinja_loader(self):
        """Flask needs every blueprint to have a jinja_loader."""
        return None


class ResponseBlueprint(Blueprint):
    """Like a blueprint but decorates the routes and has crudify funcs."""
    links = []
    cors_rules = []

    def __init__(self, name, decorators, import_name='', crudify_funcs=None,
                 default_options=None, permissions=None,
                 graphql_session_func=None, **kwargs):
        """
        :param name: (string): Name of blueprint.
        :param decorators: (list): List of functions that will decorate routes.
        :param import_name: (string): import name.
        :param crudfiy_funcs: (dict): Key is a crudify method, value is a
            function.
        :param default_options: (dict): Dictionary with default values for
            decorators on this blueprints routes.
        :param permissions: (dict): Dictionary where keys are permissions and
            values are human readable strings.
        :param graphql_session_func: (func): Function when executed returns
            a SqlAlchemy session to be used with graphql views.
        """
        super(ResponseBlueprint, self).__init__(name, import_name, **kwargs)
        self.decorators = decorators
        self.crudify_funcs = crudify_funcs or {}
        self.default_options = default_options or {}
        self.permissions = permissions
        self.graphql_session_func = graphql_session_func

    def route(self, rule, **options):
        """Wrap view with api response decorators, make `self.link`."""
        link = {'url': self.url_prefix + rule}
        link.update(options)
        self.links.append(link)

        options = self.options(options)
        permission = options.get("permission")
        if permission and permission not in self.permissions:
            raise Exception("'{}' is not a valid permission: {}".format(
                permission, sorted(self.permissions.keys())
            ))

        def decorator(f):
            endpoint = options.pop("endpoint", f.__name__)
            for decorator in self.decorators:
                v = options.pop(decorator.__name__, None)
                args = [f] if v is None else [f, v]
                f = decorator(*args)
            options.update(self.default_route_options)
            self.add_url_rule(rule, endpoint, f, **options)
            return f
        return decorator

    def graphql_view(self, rule, schema, session=None, **options):
        session = session or self.graphql_session_func()
        view = GraphQLView.as_view(
            rule, schema=schema, graphiql=True, context={'session': session})
        self.route(rule, methods=['GET', 'POST'], format_=False, **options)(view)

    def options(self, options):
        """Return a complete list of options for route and decorators."""
        complete = deepcopy(self.default_options)
        complete.update(options)
        return complete

    @property
    def default_route_options(self):
        """Return deffault options that will be passed to every route."""
        return {"strict_slashes": False}

    def crudify(self, url, model, create_form=None, update_form=None, ignore=[],
                permission={}, **kwargs):
        """Generates Create, Read, Update, and Delete endpoints.

        :param url: The base url string for each endpoint.
        :param model: The model for creating the endpoints.
        :param create_form: Form to use for creation.
        :param update_form: Form to use for update.
        :param ignore: Do not create endpoints for this list of methods.
        :param permission: Dictionary of permissions for each method. Ex:
            permissions = {
                "GET":     "perm",
                "GET ONE": "perm",
                "POST":    "perm",
                "PUT":     "perm",
                "DELETE":  "perm",
            }
        """
        if not update_form:
            update_form = create_form

        def get_func():
            return construct_query(model), success_code

        def get_one_func(id):
            instance = model.query.get_or_404(id)
            instance.confirm_owner()
            return instance, success_code

        def post_func():
            form = create_form(request.form)
            if form.validate():
                instance = form.create_obj()
                return instance, post_success_code
            return form.format_errors(), error_code

        def put_func(id):
            instance = model.query.get_or_404(id)
            instance.confirm_owner()
            form = update_form(request.form, instance=instance)
            if form.validate():
                instance = form.update_obj(instance)
                return instance, success_code
            return form.format_errors(), error_code

        def delete_func(id):
            instance = model.query.get_or_404(id)
            instance.confirm_owner()
            instance.delete()
            return empty_success_code

        funcs = (
            ("GET", self.crudify_funcs.get("GET") or get_func),
            ("GET ONE", self.crudify_funcs.get("GET ONE") or get_one_func),
            ("POST", self.crudify_funcs.get("POST") or post_func),
            ("PUT", self.crudify_funcs.get("PUT") or put_func),
            ("DELETE", self.crudify_funcs.get("DELETE") or delete_func),
        )

        for method, func in funcs:
            if method not in ignore:
                self.route_crudify_method(
                    url, model, method, func, permission.get(method), **kwargs)

    def route_crudify_method(self, url, model, method, func, permission, **kwargs):
        """Adds the crudify methods as actual routes to the blueprint."""
        method_url = url
        func.__name__ = "{}_{}".format(method, model.__name__)
        if inspect.getargspec(func).args:
            method_url += "/<int:id>"
        methods = [method.split(' ')[0]]
        kwargs["methods"] = methods
        if permission:
            kwargs["permission"] = permission
        self.route(method_url, **kwargs)(func)
