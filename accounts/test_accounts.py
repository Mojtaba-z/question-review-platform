"""Pytest coverage for authentication serializers, services, and endpoints."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken

from accounts.constants import STUDENT_GROUP, TEACHER_GROUP
from accounts.models import Student
from accounts.serializers import RegisterSerializer
from accounts.services.authentication import AccountService
from accounts.services.roles import RoleService

pytestmark = pytest.mark.django_db


def test_registration_serializer_requires_grade():
    """Reject a registration payload missing the student grade.

    Input: Username and password without grade.
    Output: Invalid serializer with a ``grade`` field error.
    """

    serializer = RegisterSerializer(data={
        'username': 'learner', 'password': 'safe-pass-123',
    })
    assert not serializer.is_valid()
    assert 'grade' in serializer.errors


def test_register_service_creates_student_and_group():
    """Create a student account and issue its access token.

    Input: Valid registration fields with grade three.
    Output: Profile, student group, view permission, and a JWT whose user ID
    identifies the new account regardless of claim serialization type.
    """

    result = AccountService.register({
        'username': 'learner', 'email': '', 'password': 'safe-pass-123', 'grade': 3,
    })
    user = get_user_model().objects.get(username='learner')
    assert Student.objects.get(user=user).grade == 3
    assert user.groups.filter(name=STUDENT_GROUP).exists()
    assert user.has_perm('question_bank.view_questionitem')
    assert str(AccessToken(result['access'])['user_id']) == str(user.pk)


def test_role_service_replaces_only_role_groups(student_user):
    """Change platform roles while preserving an unrelated Django group.

    Input: Student user also added to an ``other`` group, then assigned teacher.
    Output: Teacher and other memberships remain; student membership is gone.
    """

    other = Group.objects.create(name='other')
    student_user.groups.add(other)
    RoleService.assign_role(student_user, TEACHER_GROUP)
    assert student_user.groups.filter(name=TEACHER_GROUP).exists()
    assert not student_user.groups.filter(name=STUDENT_GROUP).exists()
    assert student_user.groups.filter(name='other').exists()


def test_register_is_student_only(api_client):
    """Prevent public registration from granting the teacher role.

    Input: Standard student signup followed by signup requesting teacher role.
    Output: HTTP 201 with student group, then HTTP 400 for teacher request.
    """

    response = api_client.post(reverse('register'), {
        'username': 'student1', 'password': 'safe-pass-123', 'grade': 3,
    }, format='json')
    assert response.status_code == 201
    user = get_user_model().objects.get(username='student1')
    assert user.groups.filter(name=STUDENT_GROUP).exists()
    assert not user.groups.filter(name=TEACHER_GROUP).exists()

    rejected = api_client.post(reverse('register'), {
        'username': 'teacher2', 'password': 'safe-pass-123',
        'grade': 3, 'role': TEACHER_GROUP,
    }, format='json')
    assert rejected.status_code == 400


def test_login_and_refresh_return_jwts(api_client):
    """Log in a user and exchange the refresh token.

    Input: Valid credentials and the refresh JWT returned by login.
    Output: HTTP 200 for both requests and a new access JWT.
    """

    get_user_model().objects.create_user('teacher1', password='safe-pass-123')
    login = api_client.post(reverse('login'), {
        'username': 'teacher1', 'password': 'safe-pass-123',
    }, format='json')
    assert login.status_code == 200
    refreshed = api_client.post(
        reverse('refresh'), {'refresh': login.data['refresh']}, format='json'
    )
    assert refreshed.status_code == 200
    assert 'access' in refreshed.data


def test_invalid_auth_input_is_rejected(api_client):
    """Report account conflicts and failed authentication through the API.

    Input: Duplicate signup, wrong login password, and malformed refresh JWT.
    Output: HTTP 400, 401, and 401 respectively.
    """

    get_user_model().objects.create_user('taken', password='safe-pass-123')
    duplicate = api_client.post(reverse('register'), {
        'username': 'taken', 'password': 'safe-pass-123', 'grade': 3,
    }, format='json')
    bad_login = api_client.post(reverse('login'), {
        'username': 'taken', 'password': 'wrong',
    }, format='json')
    bad_refresh = api_client.post(reverse('refresh'), {'refresh': 'bad'}, format='json')
    assert duplicate.status_code == 400
    assert bad_login.status_code == 401
    assert bad_refresh.status_code == 401
