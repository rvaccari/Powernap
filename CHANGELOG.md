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
