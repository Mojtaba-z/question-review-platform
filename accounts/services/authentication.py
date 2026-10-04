"""Registration, login, and JWT refresh operations."""

from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.constants import STUDENT_GROUP
from accounts.exception import AccountInputError, InvalidCredentials
from accounts.models import Student
from accounts.services.roles import RoleService


class AccountService:
    """Provide the account operations called by the authentication API.

    Registration persists a Django user and student profile, assigns the
    student group, and issues JWTs. Login and refresh delegate credential or
    token verification to Django and SimpleJWT respectively.
    """

    @staticmethod
    @transaction.atomic
    def register(data):
        """Create a student account from serializer-validated fields.

        User, profile, and role assignment share a database transaction so a
        failure cannot leave a partially registered account. Password hashing
        is performed by Django's ``create_user`` method.

        Args:
            data: Mapping with username, password, grade, and optional email.

        Returns:
            Public user fields plus access and refresh JWT strings.

        Raises:
            AccountInputError: If the username is taken or persistence fails.
        """

        user_model = get_user_model()
        if user_model.objects.filter(username=data['username']).exists():
            raise AccountInputError({'username': ['This username is already taken.']})
        try:
            user = user_model.objects.create_user(
                username=data['username'],
                email=data.get('email', ''),
                password=data['password'],
            )
            Student.objects.create(user=user, grade=data['grade'])
            RoleService.assign_role(user, STUDENT_GROUP)
        except IntegrityError as error:
            raise AccountInputError('Could not create this account.') from error
        return AccountService._token_pair(user)

    @staticmethod
    def login(request, data):
        """Authenticate credentials with Django and issue a token pair.

        Args:
            request: The current HTTP request for Django's auth backend.
            data: Mapping with serializer-validated username and password.

        Returns:
            Public user fields plus access and refresh JWT strings.

        Raises:
            InvalidCredentials: If no active user matches the credentials.
        """

        user = authenticate(
            request,
            username=data['username'],
            password=data['password'],
        )
        if user is None:
            raise InvalidCredentials()
        return AccountService._token_pair(user)

    @staticmethod
    def refresh(data):
        """Validate a refresh JWT and issue a new access JWT.

        Args:
            data: Mapping containing the submitted ``refresh`` token string.

        Returns:
            A mapping containing one new ``access`` token string.

        Raises:
            InvalidCredentials: If SimpleJWT rejects the token or it expired.
        """

        try:
            refresh = RefreshToken(data['refresh'])
        except TokenError as error:
            raise InvalidCredentials('Invalid or expired refresh token.') from error
        return {'access': str(refresh.access_token)}

    @staticmethod
    def _token_pair(user):
        """Build the shared response shape for registration and login.

        Args:
            user: Active Django user for whom SimpleJWT will issue tokens.

        Returns:
            A mapping with public user fields and access and refresh tokens.
            The password and other private user fields are not returned.
        """

        refresh = RefreshToken.for_user(user)
        return {
            'user': {'id': user.pk, 'username': user.username, 'email': user.email},
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }
