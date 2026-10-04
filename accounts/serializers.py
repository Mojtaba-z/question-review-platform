"""Request serializers for the authentication endpoints."""

from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    """Check the shape of a public student-registration request.

    Input is JSON with ``username``, ``password``, ``grade`` (1–12), and an
    optional ``email``. A valid serializer exposes those primitive values in
    ``validated_data`` for ``AccountService.register``. It does not write a user
    or allow the caller to choose a role; the view rejects a supplied role.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    grade = serializers.IntegerField(min_value=1, max_value=12)


class LoginSerializer(serializers.Serializer):
    """Check that a login request supplies credentials.

    Input is JSON with ``username`` and ``password``. Output is those strings
    in ``validated_data``; checking whether they match a user is the account
    service's responsibility. The password is never included in serialized
    output.
    """

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class RefreshSerializer(serializers.Serializer):
    """Check that a token-refresh request contains a token string.

    Input is JSON with ``refresh``. Output is the string in ``validated_data``.
    Signature, expiry, and token type are checked later by the account service.
    """

    refresh = serializers.CharField()
