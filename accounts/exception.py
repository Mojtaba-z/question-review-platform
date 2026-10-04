"""API errors raised by account services."""

from rest_framework.exceptions import APIException


class AccountInputError(APIException):
    """Return HTTP 400 for malformed or conflicting account input.

    Views and account services use this instead of exposing serializer or
    database exceptions. The detail may be a message or field-error mapping.
    """

    status_code = 400
    default_detail = 'Invalid account input.'


class InvalidCredentials(APIException):
    """Return HTTP 401 when credentials or a refresh token cannot be trusted.

    This keeps failed authentication distinct from a malformed request, which
    uses ``AccountInputError`` and HTTP 400.
    """

    status_code = 401
    default_detail = 'Invalid username or password.'
