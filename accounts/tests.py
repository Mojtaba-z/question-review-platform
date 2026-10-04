"""Serializer, service, and endpoint tests for authentication."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.constants import STUDENT_GROUP, TEACHER_GROUP
from accounts.models import Student
from accounts.serializers import RegisterSerializer
from accounts.services.authentication import AccountService
from accounts.services.roles import RoleService


class AccountServiceTests(TestCase):
    """Exercise account serializers and services without an HTTP request.

    Each test gets its own database state and checks either a validation rule
    or a role/account side effect directly.
    """

    def test_registration_serializer_requires_grade(self):
        """Check that a grade is required before registration reaches the service.

        The serializer should be invalid and name ``grade`` in its field errors.
        """

        serializer = RegisterSerializer(data={'username': 'learner', 'password': 'safe-pass-123'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('grade', serializer.errors)

    def test_register_service_creates_student_and_group(self):
        """Verify registration's database and token side effects together.

        The service must create a profile with grade three, assign the student
        group and question-view permission, and issue a token for that user.
        """

        result = AccountService.register({
            'username': 'learner', 'email': '', 'password': 'safe-pass-123', 'grade': 3,
        })
        user = get_user_model().objects.get(username='learner')
        self.assertEqual(Student.objects.get(user=user).grade, 3)
        self.assertTrue(user.groups.filter(name=STUDENT_GROUP).exists())
        self.assertTrue(user.has_perm('question_bank.view_questionitem'))
        self.assertEqual(AccessToken(result['access'])['user_id'], user.pk)

    def test_role_service_replaces_only_role_groups(self):
        """Verify exclusive platform roles preserve unrelated Django groups.

        A user moves from student to teacher while remaining in an independent
        ``other`` group that the role service does not manage.
        """

        from django.contrib.auth.models import Group

        user = get_user_model().objects.create_user('member', password='safe-pass-123')
        other = Group.objects.create(name='other')
        user.groups.add(other)
        RoleService.assign_role(user, STUDENT_GROUP)
        RoleService.assign_role(user, TEACHER_GROUP)
        self.assertTrue(user.groups.filter(name=TEACHER_GROUP).exists())
        self.assertFalse(user.groups.filter(name=STUDENT_GROUP).exists())
        self.assertTrue(user.groups.filter(name='other').exists())


class AuthenticationEndpointTests(APITestCase):
    """Exercise the public authentication routes through DRF's test client.

    These tests check response codes, returned tokens, student-only signup,
    and error handling as a client would observe them.
    """

    def test_register_is_student_only(self):
        """Check the public signup cannot grant teacher privileges.

        A normal request creates a student, while a request containing a
        teacher role is rejected with HTTP 400.
        """

        response = self.client.post(reverse('register'), {
            'username': 'student1', 'password': 'safe-pass-123',
            'grade': 3,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username='student1')
        self.assertTrue(user.groups.filter(name=STUDENT_GROUP).exists())
        self.assertFalse(user.groups.filter(name=TEACHER_GROUP).exists())
        rejected = self.client.post(reverse('register'), {
            'username': 'teacher2', 'password': 'safe-pass-123',
            'grade': 3, 'role': TEACHER_GROUP,
        }, format='json')
        self.assertEqual(rejected.status_code, 400)

    def test_login_and_refresh_return_jwts(self):
        """Check a user can log in and exchange the returned refresh JWT.

        Successful login returns HTTP 200; the refresh endpoint returns a new
        access token from that login's refresh token.
        """

        get_user_model().objects.create_user('teacher1', password='safe-pass-123')
        login = self.client.post(reverse('login'), {
            'username': 'teacher1', 'password': 'safe-pass-123',
        }, format='json')
        self.assertEqual(login.status_code, 200)
        refreshed = self.client.post(
            reverse('refresh'), {'refresh': login.data['refresh']}, format='json'
        )
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn('access', refreshed.data)

    def test_invalid_auth_input_is_rejected(self):
        """Check account conflicts and failed authentication status codes.

        Duplicate registration is bad input (400), while an incorrect password
        or malformed refresh token is an authentication failure (401).
        """

        get_user_model().objects.create_user('taken', password='safe-pass-123')
        duplicate = self.client.post(reverse('register'), {
            'username': 'taken', 'password': 'safe-pass-123', 'grade': 3,
        }, format='json')
        bad_login = self.client.post(reverse('login'), {
            'username': 'taken', 'password': 'wrong',
        }, format='json')
        bad_refresh = self.client.post(reverse('refresh'), {'refresh': 'bad'}, format='json')
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(bad_login.status_code, 401)
        self.assertEqual(bad_refresh.status_code, 401)
