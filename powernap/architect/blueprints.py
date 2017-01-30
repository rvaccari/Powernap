import inspect

from flask import Blueprint, current_app, request
from flask_login import LoginManager

from powernap.architect.loaders import init_view_modules
from powernap.architect.requests import ApiRequest
from powernap.architect.responses import format_api_response, APIEncoder
from powernap.auth.decorators import (
    require_login,
    require_permissions,
    require_public,
)
from powernap.auth.rate_limit import check_rate_limit
from powernap.auth.token import (
    user_from_redis_token_wrapper,
    request_user_wrapper,
)
from powernap.cors import init_cors
from powernap.exceptions import ApiError, api_error
from powernap.http_codes import (
    empty_success_code,
    error_code,
    post_success_code,
    success_code,
)
from powernap.query.transformer import construct_query


class Architect:
    "Registers multiple :class:`powernap.architect.blueprints.ResponseBlueprint`."
    blueprints = []

    def __init__(self, version=1, prefix=None, base_dir="", template_dir="",
                 name="architect", response_blueprint=None,
                 route_decorator_func=None, login_manager=None, user_class=None,
                 user_loader=None, api_encoder=None,
                 before_request_funcs=None, after_request_funcs=None):
        """
        :param version: (int) version number for endpoints registerd with this
            architect.
        :param prefix: (string) a url prefix to append to all endpoints.
            Requires '{}' to format in the version number. If not provided
            `current_app.config["API_URL_PREFIX"] will be used.
        :param base_dir: (string) the full path of the base directory of the
            Flask application.
        :param template_dir: (string) the full path of the template directory
        :param name: (string) a name for this architect
        :param response_blueprint: (class): class used for flask blueprints.
            Must inherit from `ResponseBlueprint`.
        :param route_decorator_funcs: (function): receives and returns a list
            of decorators that will be applied to an endpoint. This function
            can be used to override, add to, or subtract from the default
            decorators applied to endpoints.
        :param login_manager: (class): Instance of `flask_login.LoginManager`
            used to set current_user value.
        :param user_class: (class): Class that `user_from_redis_token` should
            return an instance of for the `current_user`.
        :param user_loader: (func): function for
            `login_manager.requreset_loader`
        :param api_encoder: (class): Json encoder to be used by the application.
        :param before_request_funcs: (list): List of functions to run
            before requests.
        :param after_request_funcs: (list): List of functions to run
            after requests.
        """
        self.version = version
        self._prefix = prefix
        self.base_dir = base_dir
        self.template_dir = template_dir
        self.name = name
        self.response_blueprint = response_blueprint or ResponseBlueprint
        self._crudify_funcs = {
            v: None for v in ("GET", "GET ONE", "PUT", "POST", "DELETE")
        }
        self.route_decorator_func = route_decorator_func or (lambda x: x)
        self._init_login_manager(login_manager, user_loader, user_class)
        self.api_encoder = api_encoder or APIEncoder
        self.before_request_funcs = before_request_funcs or [check_rate_limit]
        self.after_request_funcs = after_request_funcs or []

    def _init_login_manager(self, login_manager, user_loader, user_class):
        if not user_loader and not user_class:
            raise Exception(
                'Define either the "user_loader" or "user_class" kwarg.')
        user_loader = user_loader or user_from_redis_token_wrapper(user_class)
        self.login_manager = login_manager or LoginManager()
        self.login_manager.request_loader(request_user_wrapper(user_loader))

    def init_app(self, app):
        with app.app_context():
            app.json_encoder = self.api_encoder
            self.login_manager.init_app(app)
            app.register_blueprint(self)
            app.request_class = ApiRequest
            app.register_error_handler(ApiError, api_error)
            app.register_error_handler(404, api_error)
            init_cors(app)

    @property
    def crudify_funcs(self):
        return self._crudify_funcs

    @crudify_funcs.setter
    def crudify_funcs(self, **kwargs):
        self.crudify_funcs.update(kwargs)

    @property
    def prefix(self):
        prefix = self._prefix or current_app.config["API_URL_PREFIX"]
        return prefix.format(version=self.version)

    def sub_blueprint(self, name, url_prefix='', **kwargs):
        """Create a new Blueprint for the Architect to register.

        Should only be invoked in the top of files named `views.py`.
        """
        kwargs.update({
            'url_prefix': "/".join((self.prefix, url_prefix)),
            'template_folder': self.template_dir,
            "crudify_funcs": self.crudify_funcs,
        })
        blueprint = self.response_blueprint(name, **kwargs)
        blueprint.decorators = self.update_route_decorators()
        for func in self.before_request_funcs:
            blueprint.before_request(func)
        for func in self.after_request_funcs:
            blueprint.after_request(func)
        self.blueprints.append(blueprint)
        return blueprint

    def update_route_decorators(self):
        """Pass a function to update the decorated routes."""
        return self.route_decorator_func(self.default_decorators)

    @property
    def default_decorators(self):
        """Default decorators for each endpoint (kwarg, func, default value)."""
        return [
            ("public", require_public, False),
            ("login", require_login, True),
            ("permissions", require_permissions, {}),
            ("format_", format_api_response, True),
        ]

    def register(self, app, options, first_registration):
        init_view_modules(self.base_dir)
        for blueprint in self.blueprints:
            app.register_blueprint(blueprint, **options)


class ResponseBlueprint(Blueprint):
    """Like a blueprint but checks permissions & returns api responses."""
    links = []
    cors_rules = []

    def __init__(self, name, import_name='', public=False, crudify_funcs={},
                 **kwargs):
        super(ResponseBlueprint, self).__init__(name, import_name, **kwargs)
        self.public = public
        self._route_decorators = []
        self.crudify_funcs = crudify_funcs

    def route(self, rule, **options):
        """Wrap view with api response decorators, make `self.link`."""
        link = {'url': self.url_prefix + rule}
        link.update(options)
        if link.get('permissions'):
            link[self.name] = link['permissions']
            del link['permissions']
        self.links.append(link)

        def decorator(f):
            endpoint = options.pop("endpoint", f.__name__)
            for name, decorator, default_value in self.decorators:
                f = decorator(f, options.pop(name, default_value))
            options.update(self.default_route_options)
            self.add_url_rule(rule, endpoint, f, **options)
            return f
        return decorator

    @property
    def default_route_options(self):
        return {"strict_slashes": False}

    def crudify(self, url, model, create_form=None, update_form=None, ignore=[],
                permissions={}, **kwargs):
        """Generates Create, Read, Update, and Delete endpoints.

        :param url: The base url string for each endpoint.
        :param model: The model for creating the endpoints.
        :param create_form: Form to use for creation.
        :param update_form: Form to use for update.
        :param ignore: Do not create endpoints for this list of methods.
        :param permissions: Dictionary of permissions for each method. Ex:
            permissions = {
                "GET":     ['can_view'],
                "GET ONE": ['can_view'],
                "POST":    ['can_edit'],
                "PUT":     ['can_edit'],
                "DELETE":  ['can_edit'],
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
                    url, model, method, func, permissions, **kwargs)

    def route_crudify_method(self, url, model, method, func, all_permissions,
                             **kwargs):
        method_url = url
        func.__name__ = "{}_{}".format(method, model.__name__)
        permissions = all_permissions.get(method)
        if inspect.getargspec(func).args:
            method_url += "/<int:id>"
        methods = [method.split(' ')[0]]
        self.route(
            method_url,
            methods=methods,
            permissions=permissions,
            **kwargs
        )(func)
