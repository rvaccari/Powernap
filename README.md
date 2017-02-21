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

**NOTE**: these blueprints must be initialized in files names `views.py` otherwise the loader won't find them.


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
        "powernap.decorators.permission",
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


### permission

This function signals that a user needs explicit permission to access this endpoint. See permissions below. 

Kwarg defaults to `None`.

Usage: `@bp.route('/item', methods=["GET"], permission="device.edit")`


### login

This function can bypass authentication for an endpoint. 

Kwarg defaults to `True`.

Usage: `@bp.route('/item', methods=["GET"], login=False)`


### public

This function allows non admin user's to access an endpoint. 

Kwarg defaults to `False`.

Usage: `@bp.route('/item', methods=["GET"], public=True)`


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

## api_response

One of the major benifits of using powernap is that the Api Response object lets you easily define data top be sent ot the client from a model.
With powernapp an endpoint that receives the `format_` decorator can return any instance of a model.  The ApiResponse object will look for an `api_response` method on the model and automatically run it and JSON serialize the data to return to the user.

Usage:

```python
class MyModel(PowernapMixin, db.Model):
    id = Column(Integer, primary_key=True) 
    name = Column(String(255)) 
    age = Column(Integer) 
    social_security = Column(Integer) 

    def api_response(self):
        return {
            "name": self.name
            "age": self.age,
        }
```

```python
from powernap.http import success_code

bp = architect.sub_blueprint('my_model', url_prefix='/my-model')

@bp.route('/<int:id>', methods=['GET'], public=True)
def my_model(id):
    instance = MyModel.get_or_404(id)
    instance.confirm_owner()
    return instance, success_code

```

Returns `200` response with `{"name": "john doe", "age": 28}` as the json body (not containing `social_security` value).

**This also works with a list of instances.**

```python
@bp.route('/models', methods=['GET'], public=True)
def model(id):
    instances = MyModel.query.all()
    return instances, success_code
```

Returns `200` response with `[{"name": "David Bledsoe", "age": 19}, {"name": "Larry Farnell", "age": 72}, {"name": "john doe", "age": 28}]` as the json body.

**Or regular python data structures.**

```python
@bp.route('/stuff', methods=['GET'], public=True)
def model(id):
    instances = MyModel.query.all()
    return {"one": [1,2,3], "two": "hello world"}, success_code
```

Returns `200` response with `{"one": [1,2,3], "two": "hello world"}` as the json body.


## Rate limiting

By default all requests will be checked against a rate limit and all responses returned by Sub Blueprint routes will have rate limiting values in their header.
The rate limiting information is stored in redis.

Rate limiting can be disbabled in the app settings like this: `RATE_LIMITING = False`.

### Settings

- `REQUESTS_PER_HOUR`: How many non authenticated requests per hour, per user are allowed.
- `AUTHENTICATED_REQUESTS_PER_HOUR`: How many authenticated requests per hour, per user are allowed.
- `RATE_LIMIT_EXPIRATION`: Number of seconds until the rate limit expires. (This is the value passed as the TTL for the redis key).

### Headers

- 'X-RateLimit-Limit': The upper limit for the current user.
- 'X-RateLimit-Remaining': How many requests the current user has remaining in this time block.
- 'X-RateLimit-Reset': How many seconds until the rate limit resets.

**TODO: Allow Rate-limiting an IP per hour.

# Forms

When submitting a form to create or update a database entry you do not want users to update their models to be owned by other users and vice versa.  The `PowernapFormMixin` takes care of this.
*Note: This mixin has only been tested with WTForms.*

Your views can return `form.format_errors()` to ensure that errors are returned from the API in the same format everytime.

## PowernapFormMixin

```python
from powernap.mixins import PowernapFormMixin
from wtforms import Form, IntegerField, StringField, validators

from my.module import MyModel


class MyModelForm(PowernapFormMixin, Form):
    model = MyModel

    id = IntegerField(validators=[validators.DataRequired()]
    name = StringField(validators=[validators.DataRequired()]
```


# Crudify

Typically, basic CRUD funcitonality for models is repetitive.  THe crudify function aims to speed up the process of writing those endpoints by providing pre-written views that implement CRUD functionality.
For crudify to work your form must inherit from `Powernap.mixins.PowernapFormMixin`.

```python
bp = architect.sub_blueprint('model', url_prefix='/model', public=True)

# Will create GET, GET ONE, PUT, POST, and DELETE endpoints for the MyModel
# class and use the MyModelForm for the PUT and POST requests.
bp.crudify('/', MyModel, MyModelForm)
```

Crudify accepts the following additional kwargs:

- `update_form`: Form to use for PUT method.  Will use the create_form if not provided..
- `ignore`: Do not create endpoints for this list of methods. Ex. `["PUT", "POST"]`.
- `needs_permission`: Dictionary settings needs_permission for each method. Ex:
```python
    {
        "GET":     False,
        "GET ONE": False,
        "POST":    True,
        "PUT":     True,
        "DELETE":  True,
    }
```
- `kwargs`: Any additional kwargs you want passed to the `route` function.

You can pass your own crudify funcs as a dictionary to the architect object where the key is the method (`GET`) and the value is the function.

These are the methods used by crudify by defualt:

```python
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
```

**TODO: Allow passing of all decorators to the crudify methods in the same manner as needs_permission**


# Permissions

By default all Archietct Sub Blueprint routes are wrapped with a permissions decorator.  In order to make use of the functionality the following mixins need to be used.

The architect will need to be initialized with a kwarg named `permissions` what is a dictionary where keys are permission strings
and values are their human readable counterparts.

Permissions strings should be `.` seperated values where values are one word using only chars.  e.g. `device` or `device.edit`.
Perms are recursive so any user with the "device.edit" permission would also have the "device" permission.

Checks are done via a `like` query to the database.  So a route requiring `device`  will make the query 
`SELECT * FROM powernap_permissions WHERE permission LIKE 'device%';`.  So that would match `device.edit`.
This allows heirchies.  Be careful though:  a `device-stuff` permission would match like query of `device%` also.


## PermissionTableMixin

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

## PermissionUserMixin

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

Implementing a way to query models via an API can be time consuming. Powernap comes with builtin methods to read query args out of the url to perform data queries.

## Query Params

The 4 different types of special arguments:

1. Keys that are unique fields on the model. e.g. `/api/v1/my-model?name=john`
2. A $ followed by keys that are methods on a SQLAlchemy session such as order_by. e.g. $order_by=client_id.
3. A $ followed by one or more of the unique query methods below. e.g. $subject__icontains=hello.
4. A $ followed by one or more of the pagination query args page and per_page.

### Unique Query Methods

- **FIELD__not_eq**: Will return any object who’s FIELD is not equal to the value `cls.query.filter(func.(getattr(cls, FIELD) != value))`
- **FIELD__icontains**: Searches a field to see if it contains the value. `cls.query.filter(func.LOWER(getattr(cls, FIELD)).contains(value.lower())`.
- **FIELD__inside**: Will return any object who’s FIELD is inside the value list. `cls.query.filter(cls.FIELD.in_(value))`.
- **FIELD__not_inside**: Will return any object who’s FIELD is not inside the value list. `cls.query.filter(~cls.FIELD.in_(value))`.
- **FIELD__gt**: Will return any object who’s FIELD is greater than the value. `cls.query.filter(cls.FIELD > value)`.
- **FIELD__gte**: Will return any object who’s FIELD is greater than or equal to the value. `cls.query.filter(cls.FIELD >= value)`.
- **FIELD__lt**: Will return any object who’s FIELD is less than the value. `cls.query.filter(cls.FIELD < value)`.
- **FIELD__lte**: Will return any object who’s FIELD is less than or equal to the value. `cls.query.filter(cls.FIELD <= value)`.
- **FIELD__like**: Will return any object’s FIELD who’s value matches a sql like query. `cls.query.filter(cls.FIELD).like(value)`.
- **FIELD__max**: Will return the max value in  FIELD. `cls.query.filter(func.max(cls.FIELD))`.
- **FIELD__min**: Will return the min value in  FIELD. `cls.query.filter(func.min(cls.FIELD))`.

Example: `/api/v1/my-model?$name__like=jo%`

## construct_query

`from powernap.query.transformer import construct_query`

Pass a model to this function and it will return a sqlalchemy query of that model based on the query_args in the param.

`construct_query(MyModel)` with query_args `name="john"` will run `MyModel.query.filter_by(name="john").all().  If only one object is in the list it will return only that one object.
If multiple objects are in the list, it will return a pagination object

By default `enforce_owner` kwarg is true and will use the `ACTIVE_TOKENS_ATTR` and `DB_ENTRY_ATTR` to override the query args to ensure that the current user can only query for models belonging to them (if the model does not have the `DB_ENTRY_ATTR` field then this functinality is ignored).


## exposed_fields

Sometimes you do not want the user to be able to query by every field in the database. By default the user cannot query by any fields until they are exposed.  To expose a field add an `exposed_fields` attr tot he model.

```python
class MyModel(PowernapMixin, db.Model):

    exposed_fields = [
        "id",
        "name",
    ]

    id = Column(IntegerField())
    name = Column(StringField(255))
    social = Column(StringField(255))
```
The user will only be able to query by `id` and `name` with `construct_query` via query args.


## extend_query

`from powernap.query.transformer import extend_query`

This method is for using `construct_query` like functionality but with an already started query.

```python
query = MyModel.query.filter_by(name="john")
extend_query(query, ignore=["name"])
```

This will query name = john regarless of if the user passed a name value in the query args.

## Pagination

By default construct_query will paginate the results.  The pagination data is passed to the client via the Link header:

```
Link:
<https://api.hivelocity.net/api/v1/URL_AND_ARGS&page=FIRST_PAGE>; rel="first",
<https://api.hivelocity.net/api/v1/URL_AND_ARGS&page=PREV_PAGE>; rel="prev",
<https://api.hivelocity.net/api/v1/URL_AND_ARGS&page=NEXT_PAGE>; rel="next",
<https://api.hivelocity.net/api/v1/URL_AND_ARGS&page=LAST_PAGE>; rel="last"
```
**IMPORTANT**: This Link header does not follow all specifications in [RFC 5988](https://tools.ietf.org/html/rfc5988), and the links above are returned in no specific order.

### Settings

- `PAGINATION_PAGE`: default pagination page
- `PAGINATION_PER_PAGE`: default # of instances per page.

## Custom Columns


By default Integer, Boolean, String, and DateTime columns are supported.  Other sqlalchemy column types need custom columns in order to work with Easy Query methods.
Columns handle implementing the various query arg methods depending upon the field type of a particular query arg.

To add custom query column create a new column form the `BaseQueryColumn` and add it to `QueryColumns`

```python
from powernap.query.columns import QUERY_COLUMNS, BaseQueryColumn
from sqlalchemy.sql.sqltyupes import String, Text

# Maybe you do not want your users to do like queries on string or text
# columns and want all the values to be converted to pig latin.

class CustomStringColumn(BaseQueryColumn):
    invalid = ["like"]

    def handle(self, column, value, func):
        value = "{}{}say".format(value[1:], value[0])
        return super().handle(column, value, func)


QUERY_COLUMNS[String] = CustomStringColumn
QUERY_COLUMNS[Text] = CustomStringColumn
```

### Settings
- `QUERY_METHOD_DECORATOR`: Function that decorates the methods that return special kwargs. *Advanced users only*
