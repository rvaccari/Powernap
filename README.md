# Powernap

A Flask-framework for developing RESTful APIs fast!
Powernap handles logic needed for most RESTful APIs so that you dont have to.


# Installation

Requires python version >= 3.4

`pip install powernap`

Powernap also requireds a [Redis](https://redis.io/) instance for token management.


# The Architect.

The `Architect` is the master object that orchestrates routing, formating, verifying, rate limiting, and all other 
major functionality of Powernap.  It does this by handling multiple Sub Blueprints.

How to initialize an Architecture object in your application.
```python
from powernap.architect.blueprints import Architect

architect = Architect(user_loader="my.module.user_loader")
architect.init_app(app)
```

Powernap makes use of **Flask-Login** to handle authenticating users.
The `user_loader` kwargs is a string of a path to your `user_loader` function that is required by [Flask Login](https://flask-login.readthedocs.io/en/latest/#how-it-works)

The architect initializes with intelligent defaults but they can be overidden.
Check the docstring for descriptions of keyword arguments.

Now that the architect is initialized it you can start registering sub blueprints and routes.

## Sub Blueprints

At the heart of Powernap are Sub Blueprints. These are like traditionaly Flask Blueprints except they wrap the routes with various decorators
that handle functionality such as authentication, sanitization, and more.  Additionally it returns an `ApiResponse` object that handles rate
limiting and filtering not permitted information out of the response.

To register a Sub Blueprint import the intialized Architect and run the `sub_blueprint` function. This is like initializing a traditional Flask Blueprint.
You can use all the kwargs available to traditional Flask Blueprints as well as the additional kwargs of the Architect decorators.
Once the Sub Blueprint is created you can route your views as normal.
Routes also take traditional Flask kwargs as well the additional kwargs of the Architect decorators.

```python
from powernap.http_codes import success_code

bp = architect.sub_blueprint('stuff', url_prefix='/stuff')

@bp.route('', methods=["GET"])
def my_stuff():
    return "stuff", success_code
```

## Decorators

Powernap's architect initialized with 5 default decorators that wrap all functions that are routed to flask.
Below are the decorators and their functionality in order.  The decorators name can be passed as a kwarg to either the sub bluprint to 
apply globally to all routes in the blueprint, or to routes individually.  If a decorator kwarg is passed to a route it will 
override any global decorator value on the Sub Blueprint.

```python
bp = architect.sub_blueprint('stuff', format_=False)

@bp.route('/stuff', methods=["GET"])
def my_stuff():
    return "stuff", success_code

@bp.route('/thing', methods=["GET"])
def my_thing():
    return "thing", success_code

@bp.route('/item', methods=["GET"], format_=True)
def my_item():
    return "item", success_code
```
By default `format_` is set to `True` (see below).
In the above code both functions `my_stuff` and `my_thing` will receive the global `format_=False` set in the Sub Blueprint and not format the response.
Contrary, the `my_item` function will format the response as its decorator kwargs override the Sub Blueprint's.

You can choose which decorators are used or use your own decorators via the Architect

```python
def otp(func, otp=True):
    def _formatter(*args, **kwargs):
        if not otp_valid():
            raise ApiError(description="OTP not valid.")
        return func(*args, **kwargs)
    return _formatter
```

```python
from my.decorators import otp

### format_

This function json serializes the response and allows views to return class instances. More on this in the **Api Response** section. 

Defaults to `True`.

Usage: `@bp.route('/item', methods=["GET"], format_=False)`


### safe

This function can bypass the use of the [bleach](https://github.com/mozilla/bleach) package to sanitize response data, removing any script and html tags. 

Defaults to `False`.

Usage: `@bp.route('/item', methods=["GET"], safe=True)`


### needs_permission

This function can signal that a user needs a special permisssionjson serializes the response and allows views to return class instances. More on this in the **Api Response** section. 

Defaults to `True`.

Usage: `@bp.route('/item', methods=["GET"], format_=False)`

## needs_permission

## Crudify


# Models

## PowernapMixin
### Special funcs

## PermissionUserMixin

## PermissionTableMixin

## Users

is_admin
