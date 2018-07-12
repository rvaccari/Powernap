07-12-18 2.0.7:

Use data.has_prev property to determine pagination. prev_num was changed
to return None when there is no prev page.

07-09-18 2.0.6:

Use data.has_next property to determine pagination. next_num was changed
to return None when there is no next page.

07-05-18 2.0.5:

Rename deprecated imports.

07-05-18 2.0.4:

Rename deprecated imports.

06-29-18 2.0.3:

Make package requirements minimum versions rather than specific.

06-27-18 2.0.2:

Fix improper use of MultiDict

06-27-18 2.0.1:

Fix two missed request.form uses. Add warning for incorrect json mimetype.

06-22-18 2.0.0:

Convert low-level json form magic code to a top-level `jsonform`
cached property on ApiRequest. This breaks the interface, so a new major version.

06-21-18 1.5.5:

Fix request.remote_addr logic to return the correct, first untrusted
address.

06-11-18 1.5.4:

Re-Fix AttributeError: 'NoneType' object has no attribute 'read'.
The last fix broke in another location. This one hacks
werkzeug.wrappers.data to avoid the problem.


06-08-18 1.5.3:

Fix AttributeError: 'NoneType' object has no attribute 'read'


09-14-17 1.5.2:

Allow comma seperated values to be passed to order by.


09-14-17 v1.2.1:

Allow SQLAlchemy Properties and API Response keys to be excluded from queries


6-07-17 v1.1.0:

Give ability to whitelist ip networks for the rate limiter


5-09-17 v1.0.5:

Add accepted 202 code to `http_codes`.


3-17-17 v1.0.4:

Fix missing jinja_loader on Architect 


2-27-17 v1.0.3:

Fix `X-Pagination` header.  Use this format {'per_page': 10, 'next': 2, 'prev': 0, 'first': 1, 'last': 10, 'total': 93, 'current': 1}


v1.0.2:

Fix bleaching so that only strings are bleached.
Add IP address to the rate limiting token.
Provide setting to disable ratelimiting.


02-01-17

All features working.  Needs refactoring for better/prettier control.
