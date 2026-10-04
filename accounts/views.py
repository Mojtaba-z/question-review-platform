"""Authentication API endpoints."""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.exception import AccountInputError
from accounts.serializers import LoginSerializer, RefreshSerializer, RegisterSerializer
from accounts.services.authentication import AccountService


class RegisterView(APIView):
    """Public endpoint for creating student accounts.

    POST ``/api/auth/register/`` accepts the registration serializer's fields.
    A client cannot choose a role; all accounts created here become students.
    Authentication is disabled so an expired bearer token cannot block signup.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """Validate registration input and return the new account and JWTs.

        Args:
            request: DRF request with username, password, grade, and email.

        Returns:
            HTTP 201 with public user fields and access/refresh tokens.

        Raises:
            AccountInputError: For a selected role or invalid input.
        """

        if 'role' in request.data:
            raise AccountInputError('Role cannot be selected during registration.')
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            raise AccountInputError(serializer.errors)
        result = AccountService.register(serializer.validated_data)
        return Response(result, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Public endpoint for obtaining JWTs with username and password.

    POST ``/api/auth/login/`` accepts credentials for any active Django user,
    including students and teachers. Authentication is disabled on this view
    so a stale bearer token does not interfere with logging in.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """Validate credentials and return tokens for the matched user.

        Args:
            request: DRF request containing username and password.

        Returns:
            HTTP 200 with public user fields and access/refresh tokens.

        Raises:
            AccountInputError: If the request shape is invalid.
            InvalidCredentials: If the credentials do not authenticate.
        """

        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            raise AccountInputError(serializer.errors)
        return Response(AccountService.login(request, serializer.validated_data))


class RefreshView(APIView):
    """Public endpoint for obtaining a new access JWT from a refresh JWT.

    POST ``/api/auth/refresh/`` does not require an existing access token.
    The refresh token itself is checked by the account service.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """Validate the request and return one new access token.

        Args:
            request: DRF request containing a ``refresh`` token string.

        Returns:
            HTTP 200 with an ``access`` token; no new refresh token is issued.

        Raises:
            AccountInputError: If the refresh field is missing or malformed.
            InvalidCredentials: If the token is invalid or expired.
        """

        serializer = RefreshSerializer(data=request.data)
        if not serializer.is_valid():
            raise AccountInputError(serializer.errors)
        return Response(AccountService.refresh(serializer.validated_data))
