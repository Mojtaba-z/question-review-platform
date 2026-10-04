"""API errors raised while importing or selecting questions."""

from rest_framework.exceptions import APIException


class QuestionInputError(APIException):
    """Return HTTP 400 when the batch itself has an invalid shape.

    Invalid individual items are collected in the import result instead, so
    one bad question does not prevent valid neighbors from being stored.
    """

    status_code = 400
    default_detail = 'Invalid question input.'


class NoAvailableQuestion(APIException):
    """Return HTTP 404 when the practice selector has no candidate.

    This covers an unknown or grade-incompatible skill as well as a skill whose
    accepted questions were all attempted recently or are otherwise absent.
    """

    status_code = 404
    default_detail = 'No eligible practice question is available.'
