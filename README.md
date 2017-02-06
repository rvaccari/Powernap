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
# my.module.decorators

def otp(func, otp=True):
    def _formatter(*args, **kwargs):
        if not otp_valid():
            raise ApiError(description="OTP not valid.")
        return func(*args, **kwargs)
    return _formatter
```

```python
Architect(
    decorators=[
        "powernap.decorators.format_",
        "powernap.decorators.safe",
        "my.module.decorators.otp",
        "powernap.decorators.needs_permission",
        "powernap.decorators.login",
    ]
)
```

### format_

This function json serializes the response and allows views to return class instances. More on this in the **Api Response** section. 

Kwarg defaults to `True`.

Usage: `@bp.route('/item', methods=["GET"], format_=False)`


### safe

This function can bypass the use of the [bleach](https://github.com/mozilla/bleach) package to sanitize response data, removing any script and html tags. 

Kwarg defaults to `False`.

Usage: `@bp.route('/item', methods=["GET"], safe=True)`


### needs_permission

This function signals that a user needs explicit permission to access this endpoint. See permissions below. 

Kwarg defaults to `False`.

Usage: `@bp.route('/item', methods=["GET"], needs_permission=True)`


### login

This function can bypass authentication for an endpoint. 

Kwarg defaults to `True`.

Usage: `@bp.route('/item', methods=["GET"], login=False)`


### public

This function allows non admin user's to access an endpoint. 

Kwarg defaults to `False`.

Usage: `@bp.route('/item', methods=["GET"], public=True)`


## Crudify


# Models 

In many API's some or all of an entry in a databse is returned to the user.  Powernap implements multiple helper utilities to make this process easier.

## PowernapMixin

Typically you will want all of your sqlalchemy db models to inherit this mixin.  This mixin has helper functions for ensuring ownership.

```python
from powernap.mixins import PowernapMixin
from sqlalchemy import Column, Integer, String

from my.extensions import initialized_sqlalchemy as db

class MyModel(PowernapMixin, db.Model):
    id = Column(Integer, primary_key=True) 
    name = Column(String(255)) 
    value = Column(String(255)) 
```

The major additional functions provided by the mixin are below. You can review `powernap.mixins` for all functions.

### confirm_owner

This function ensures that the user accessing the endpoint is indeed the owner of the instance.  A check is run confirming that the `current_user`'s primary key
is identical to an attr on the instance's (typically an attr that is a foreign key to the `current_user`).

The attr used on the `current_user` defaults to `id` but can be set via the setting `ACTIVE_TOKENS_ATTR`. (This attr will also be used by the powernap's authentication mechanism.
The attr used on the **every** model is `id` by default but can be set via the settings `DB_ENTRY_ATTR`.

When `confirm_owner` is called and the values at the attrs do not match an `OwnerError` exception is thrown and the user will get a 404.

The logic is as follows:

```python
ACTIVE_TOKENS_ATTR = "id"
DB_ENTRY_ATTR = "client_id"

# Logic based on above params
if instance.client_id != current_user.id:
    raise OwnerError
```

Usage: 

```python
instance = MyModel.query.get(1)
instance.confirm_owner()
```

### save, delete, and safe_delete

- `instance.save` will add the instance to the model's session and commit.
- `instance.delete` will delete the instance via the model's session and commit
- `MyModel.safe_delete(1)` will get the MyModel instance with primary key 1 via a `get_or_404` call.  Then it will run `confirm_owner` on the instance.  And finally run the `delete` method on the instance.

### exists, create, and get_or_create

- `MyModel.exists(**kwargs)` will quickly test if a particular model exists and return a boolean.
- `MyModel.create(**kwargs): initializes an instance of `MyModel` with `kwargs` for values and saves it to the database.
- `MyModel.get_or_create(**kwargs): returns a tuple where the first element is an instance of `MyModel` with the `kwargs` values and the second element is a boolean indicating if the instance was created.

# Api Response

One of the major 

## api_response

## Rare limiting


## Permissions

By default all Archietct Sub Blueprint routes are wrapped with a permissions decorator.  In order to make use of the functionality the following mixins need to be used.

### PermissionTableMixin

This mixin creates a table via sqlalchemy that holds permission information.  This mixin will create the following fields

- `user_id`: The primary key of the `current_user` that owns this permission
- `rule`: The `url_rule` of the `request` to which this permission applies.
- `method`: The method (`GET`, `POST`, `PUT`, `DELETE`, etc) that the permission permits.

```python
# my.module.permissions

from powernap.auth.mixins import PermissionTableMixin

from my.extensions import initialized_sqlalchemy as db


class Permission(PermissionTableMixin, db.Model):
    pass
```

### PermissionUserMixin

Your `current_user` model's must inherit from this mixin and a `permission_class` arg for the `needs_permission` decorator to work.

```python
from powernap.auth.mixins import PermissionUserMixin

from my.extensions import initialized_sqlalchemy as db
from my.module.permission import Permission


class MyUser(PermissionsUserMixin, db.Model):
    permission_class = Permission

    # Define your fields here.
```

### is_admin

If desired you may have admin user's. Admin user's bypass the public decorator as well as the `confirm_owner` function.  This is useful for actual human admins or applications that need to access everything.
To make a `current_user` an admin.  They just need to have a `is_admin` attr that is set to True.

# Authentication.

Authentication checks are handled by the Architect object, but you still need to authenticate the user via an endpoint. 
Typically you would accept a credential and a password via a form, check that are accurate then login the user via [flask_login.login_user](https://flask-login.readthedocs.io/en/latest/#flask_login.login_user).
Below is a basic approach.

```python
# my.module.token.form

from flask_login import login_user

class TokenForm(Form):
    credential = StringField(validators=[validators.DataRequired()])
    password = StringField(validators=[validators.DataRequired()])

    def validate(self, *args, **kwargs):
        is_valid = super().validate(*args, **kwargs)
        user, authenticated = my_auth_checking_method(self.data['credential'],
                                                      self.data['password'])
        if is_valid and autheticated:
            login_user(user)
            return True
        return False
```

```python
from powernap.http_codes import success_code, unprocessable_code

from my.module import architect
from my.module.token.form import TokenForm


bp = architect.sub_blueprint('token', url_prefix='/token')

# Set login and public to True so that non-admin non-authenticated users can 
# access the endpoint.
@bp.route('', methods=['POST'], login=False, public=True)
def auth():
    form = TokenForm(request.form)
    if form.validate():
        return {'token': form.api_token}, success_code
    return form.errors, unprocessable_code
```

# Easy Query
