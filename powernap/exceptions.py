"""Powernap API Errors."""

from powernap.http_codes import (
    error_code,
    not_found_code,
    forbidden_code,
    too_many_requests_code,
    unauthorized_code,
    internal_server_error_code,
)


class ApiError(Exception):
    """Triggers Flask error handler :meth:`core.api.exceptions.api_error`."""

    def __init__(self, description=None):
        """Create an ApiError with an optional description.

        :param description: A json serializable object or data structure
            that is passed to the :meth:`core.api.api_response` with
            the key `errors`.
        """
        self.description = description
        super(Exception, self).__init__()


class DatabaseError(ApiError):
    """Raise when a database error occurs."""

    code = internal_server_error_code


class InvalidFormError(ApiError):
    """Raise when user does a POST or PUT request with invalid data."""

    code = error_code


class InvalidJsonError(ApiError):
    """Raise when user does a POST or PUT request with bad JSON."""

    code = error_code


class InvalidDataFormatError(ApiError):
    """Raise when a model attr is set with an invalid data type.

    Mostly used for JSON fields.
    """

    code = error_code


# TODO Harvey - why not 401 UnauthorizedError
class OwnerError(ApiError):
    """Raise when user tries to access a db model they don't own."""

    code = not_found_code


# TODO Harvey - why not 401 UnauthorizedError
class PermissionError(ApiError):
    """Raise when user tries to access page without proper permissions."""

    code = forbidden_code


class RequestLimitError(ApiError):
    """Raise when user's session has exceeded the rate limit."""

    code = too_many_requests_code


class UnauthorizedError(ApiError):
    """Raise when anonymous user tries to access page without api token."""

    code = unauthorized_code


class UbersmithAPIError(ApiError):
    """Raise when a ResponseError is raised by the ubersmith API."""

    code = error_code
