import inspect

from flask import Blueprint, current_app, request
from flask_login import LoginManager

from architect.http_codes import (
    empty_success_code,
    error_code,
    post_success_code,
    success_code,
)
from powernap.architect.responses import format_api_response
from powernap.architect.loaders import init_view_modules
from powernap.query import construct_query
from powernap.auth.decorators import (
    require_login,
    require_permissions,
    require_public,
)
from powernap.auth.token import (
    TokenManager,
    user_from_redis_token,
    request_user_wrapper


class Architect:
    "Registers multiple :class:`core.architect.blueprints.ResponseBlueprint`."
    blueprints = []

    def __init__(self, version=1, prefix=None, base_dir="", template_dir="",
                 name="architect", response_blueprint=None,
                 route_decorator_func=None, login_manager=None,
                 user_loader=None, temp_token_class=None):
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
        :param route_decorator_func: (function): receives and returns a list
            of decorators that will be applied to an endpoint. This function
            can be used to override, add to, or subtract from the default
            decorators applied to endpoints.
        :param login_manager: (class): Instance of `flask_login.LoginManager`
            used to set current_user value.
        :param temp_token_class: (class): Class to be used as a wrapper around
            the temporary token data from redis.abs
        :param user_loader: (func): function for
            `login_manager.requreset_loader`
        """
        self.version = version
        self._prefix = prefix
        self.base_dir = base_dir
        self.template_dir = template_dir
        self.name = name
        self.response_blueprint = response_blueprint or ResponseBlueprint
        self._crudify_methods = {
            v: None for v in ("GET", "GET ONE", "PUT", "POST", "DELETE")
        }
        self._before_request_methods = []
        self._after_request_methods = []
        self.route_decorator_func = route_decorator_func or (lambda x: x)

        self._login_manager = login_manager or LoginManager()
        user_loader = request_user_wrapper(user_loader or user_from_redis_token)
        self._login_manager.request_loader(user_loader)
        self.temp_token_clas = temp_token_class

    def init_app(self, app):
        self.login_manager.init_app(app)
        app.register_blueprint(self)

    @property
    def crudify_methods(self):
        return self._crudify_methods

    @crudify_methods.setter
    def crudify_methods(self, **kwargs):
        self.crudify_methods.update(kwargs)

    @property
    def before_request_methods(self):
        return self._before_request_methods

    @before_request_methods.setattr
    def before_request_methods(self, value):
        self._before_request_methods = value

    @property
    def after_request_methods(self):
        return self._after_request_methods

    @after_request_methods.setattr
    def after_request_methods(self, value):
        self._after_request_methods = value

    @property
    def custom_route_decorators(self):
        return self._route_decorators

    @custom_route_decorators.setattr
    def custom_route_decorators(self, value):
        self._route_decorators = value

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
            "crudify_methods": self.crudify_methods,
            "custom_route_decorators": self.custom_route_decorators,
        })
        blueprint = self.response_blueprint(name, **kwargs)
        blueprint.decorators = self.update_route_decorators(blueprint)
        for func in self.before_request_methods:
            blueprint.before_request(func)
        for func in self.after_request_methods:
            blueprint.after_request(func)
        self.blueprints.append(blueprint)
        return blueprint

    def update_route_decorators(self):
        """Pass a function to update the decorated routes."""
        return self.route_decorator_func(self.default_decorators)

    @property
    def default_decorators(self):
        return [
            ("public", require_public),
            ("login", require_login),
            ("permissions", require_permissions),
            ("format_", format_api_response),
        ]

    def register(self, app, options, first_registration):
        init_view_modules(self.base_dir)
        for blueprint in self.blueprints:
            app.register_blueprint(blueprint, **blueprint.options)


class ResponseBlueprint(Blueprint):
    """Like a blueprint but checks permissions & returns api responses."""
    links = []
    cors_rules = []

    def __init__(self, name, import_name='', public=False, crudify_methods={},
                 **kwargs):
        super(ResponseBlueprint, self).__init__(name, import_name, **kwargs)
        self.public = public
        self._route_decorators = []
        self.crudify_methods = crudify_methods
        self._decorators = []

    @property
    def decorators(self):
        return self._decorators

    @decorators.setattr
    def decorators(self, value):
        self._decorators = value

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
            for name, decorator in self.decorators:
                f = decorator(f, options.pop(name))
            options.update(self.default_route_options)
            self.add_url_rule(rule, endpoint, f, **options)
            return f
        return decorator

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
            ("GET", self.crudify_methods.get("GET", get_func)),
            ("GET ONE", self.crudify_methods.get("GET ONE", get_one_func)),
            ("POST", self.crudify_methods.get("POST", post_func)),
            ("PUT", self.crudify_methods.get("PUT", put_func)),
            ("DELETE", self.crudify_methods.get("DELETE", delete_func)),
        )

        for method, func in funcs:
            if method not in ignore:
                self.route_crudify_method(method, func, permissions)

    def route_crudify_method(self, method, func, permissions):
        method_url = url
        func.__name__ = "{}_{}".format(method, model.__name__)
        perms = permissions.get(method)
        if inspect.getargspec(func).args:
            method_url += "/<int:id>"
        methods = [method.split(' ')[0]]
        self.route(
            method_url,
            methods=methods,
            permissions=permissions,
            **kwargs
        )(func)
