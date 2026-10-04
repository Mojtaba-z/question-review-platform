"""API errors raised by the practice and review services."""

from rest_framework.exceptions import APIException


class PracticeInputError(APIException):
    """Return HTTP 400 for invalid practice or reporting input.

    Views use this for serializer errors and missing student profiles; services
    use it for unavailable question IDs or unknown report filters.
    """

    status_code = 400
    default_detail = 'Invalid practice input.'


class AttemptNotFound(APIException):
    """Return HTTP 404 when a review targets a missing attempt.

    The review service raises this before attempting to change any review
    fields, so the caller can distinguish a missing ID from a repeat review.
    """

    status_code = 404
    default_detail = 'Attempt not found.'


class AttemptAlreadyReviewed(APIException):
    """Return HTTP 400 when an attempt already has a review decision.

    Both True and False count as reviewed; only ``None`` is pending. Rejecting
    a second decision keeps the first teacher's recorded judgment intact.
    """

    status_code = 400
    default_detail = 'This attempt has already been reviewed.'
