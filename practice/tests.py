"""Unit and endpoint tests for practice, review, reports, and health."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.constants import STUDENT_GROUP, TEACHER_GROUP
from accounts.models import Student
from accounts.services.roles import RoleService
from practice.exception import AttemptAlreadyReviewed, PracticeInputError
from practice.models import Attempt
from practice.serializers import ActivityQuerySerializer, AttemptSubmitSerializer, ReviewSerializer
from practice.services.attempts import AttemptService
from practice.services.reports import ActivityReportService
from question_bank.models import QuestionItem, Skill
from question_bank.services.import_questions import QuestionImportService


def create_question(item_id, status='accepted'):
    """Import and return one grade-three addition question for tests."""

    result = QuestionImportService.import_batch([{
        'id': item_id,
        'skill': 'two_digit_addition',
        'grade': 3,
        'prompt_en': f'What is {item_id} plus one?',
        'response_type': 'integer',
        'requested_difficulty': 2,
        'assessed_difficulty': None,
        'source_question_ids': ['wk_001'],
        'generation_config': {'prompt_version': 'test'},
        'validation_status': status,
        'validation_reasons': ['schema_ok'],
    }])
    if result['errors']:
        raise AssertionError(result['errors'])
    return QuestionItem.objects.get(pk=item_id)


class PracticeServiceTests(TestCase):
    """Check submission, manual review, and aggregate activity logic."""

    def setUp(self):
        """Create users, a student profile, and accepted/rejected questions."""

        Skill.objects.create(
            slug='two_digit_addition', name='Addition', grade=3,
            learning_objective='Add numbers.',
        )
        user_model = get_user_model()
        self.user = user_model.objects.create_user('student', password='safe-pass-123')
        self.teacher = user_model.objects.create_user('teacher', password='safe-pass-123')
        self.student = Student.objects.create(user=self.user, grade=3)
        self.accepted = create_question('q1')
        self.rejected = create_question('q2', 'rejected')

    def test_submission_serializer_and_pending_service(self):
        """Validate an answer and store it without automatic grading."""

        serializer = AttemptSubmitSerializer(data={
            'question_item': self.accepted.pk,
            'submitted_answer': '42',
            'time_spent_seconds': 20,
        })
        self.assertTrue(serializer.is_valid())
        attempt = AttemptService.submit(self.student, serializer.validated_data)
        self.assertIsNone(attempt.reviewed_correct)
        self.assertIsNone(attempt.reviewed_by)
        self.assertEqual(attempt.time_spent_seconds, 20)
        with self.assertRaises(PracticeInputError):
            AttemptService.submit(self.student, {
                'question_item': self.rejected.pk, 'submitted_answer': '42',
            })

    def test_serializers_reject_missing_or_invalid_inputs(self):
        """Reject missing answers, invalid review decisions, and bad report filters."""

        self.assertFalse(AttemptSubmitSerializer(data={'question_item': 'q1'}).is_valid())
        self.assertFalse(ReviewSerializer(data={'correct': 'maybe'}).is_valid())
        self.assertFalse(ActivityQuerySerializer(data={'student': -1}).is_valid())

    def test_review_sets_reviewer_and_rejects_repeat(self):
        """Persist a teacher's decision and refuse a second decision."""

        attempt = Attempt.objects.create(
            student=self.student, question_item=self.accepted, submitted_answer='42'
        )
        review = ReviewSerializer(data={'correct': False})
        self.assertTrue(review.is_valid())
        reviewed = AttemptService.review(attempt.pk, self.teacher, review.validated_data['correct'])
        self.assertIs(reviewed.reviewed_correct, False)
        self.assertEqual(reviewed.reviewed_by, self.teacher)
        with self.assertRaises(AttemptAlreadyReviewed):
            AttemptService.review(attempt.pk, self.teacher, True)

    def test_report_uses_reviewed_attempts_as_denominator(self):
        """Calculate a 50 percent result from one correct of two reviewed."""

        Attempt.objects.create(
            student=self.student, question_item=self.accepted,
            submitted_answer='a', reviewed_correct=True,
        )
        Attempt.objects.create(
            student=self.student, question_item=self.accepted,
            submitted_answer='b', reviewed_correct=False,
        )
        Attempt.objects.create(
            student=self.student, question_item=self.accepted,
            submitted_answer='c', reviewed_correct=None,
        )
        report = ActivityReportService.report(self.student.pk, 'two_digit_addition')
        self.assertEqual(report['attempts'], 3)
        self.assertEqual(report['pending'], 1)
        self.assertEqual(report['correct_percentage'], 50.0)


class PracticeEndpointTests(APITestCase):
    """Exercise every practice endpoint and its role boundary over HTTP."""

    def setUp(self):
        """Create an accepted question, student, and teacher with permissions."""

        Skill.objects.create(
            slug='two_digit_addition', name='Addition', grade=3,
            learning_objective='Add numbers.',
        )
        user_model = get_user_model()
        self.student_user = user_model.objects.create_user('student', password='safe-pass-123')
        self.teacher = user_model.objects.create_user('teacher', password='safe-pass-123')
        RoleService.assign_role(self.student_user, STUDENT_GROUP)
        RoleService.assign_role(self.teacher, TEACHER_GROUP)
        self.student = Student.objects.create(user=self.student_user, grade=3)
        self.question = create_question('q1')

    def test_next_question_is_student_only(self):
        """Return an accepted question to a student and deny the teacher."""

        url = reverse('practice-next') + '?skill=two_digit_addition'
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], 'q1')
        self.client.force_authenticate(user=self.teacher)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_next_question_reports_no_eligible_item(self):
        """Return 404 when the only question is no longer accepted."""

        QuestionItem.objects.filter(pk=self.question.pk).update(validation_status='flagged')
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(reverse('practice-next') + '?skill=two_digit_addition')
        self.assertEqual(response.status_code, 404)

    def test_login_jwt_opens_student_endpoint(self):
        """Use a real login access token to request a practice question."""

        login = self.client.post(reverse('login'), {
            'username': 'student', 'password': 'safe-pass-123',
        }, format='json')
        self.assertEqual(login.status_code, 200)
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')
        response = self.client.get(reverse('practice-next') + '?skill=two_digit_addition')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], 'q1')

    def test_submit_is_student_only_and_remains_pending(self):
        """Store a student's answer as pending and deny teacher submission."""

        url = reverse('attempt-submit')
        body = {'question_item': 'q1', 'submitted_answer': '42'}
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(url, body, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data['reviewed_correct'])
        self.assertIsNone(response.data['reviewed_by'])
        self.client.force_authenticate(user=self.teacher)
        self.assertEqual(self.client.post(url, body, format='json').status_code, 403)

    def test_pending_and_review_are_teacher_only(self):
        """Show pending answers and let only teachers review them once."""

        attempt = Attempt.objects.create(
            student=self.student, question_item=self.question, submitted_answer='42'
        )
        list_url = reverse('attempts-pending')
        review_url = reverse('attempt-review', args=[attempt.pk])
        self.client.force_authenticate(user=self.student_user)
        self.assertEqual(self.client.get(list_url).status_code, 403)
        self.assertEqual(
            self.client.patch(review_url, {'correct': True}, format='json').status_code, 403
        )
        self.client.force_authenticate(user=self.teacher)
        self.assertEqual(len(self.client.get(list_url).data), 1)
        response = self.client.patch(review_url, {'correct': True}, format='json')
        self.assertEqual(response.status_code, 200)
        attempt.refresh_from_db()
        self.assertIs(attempt.reviewed_correct, True)
        self.assertEqual(attempt.reviewed_by, self.teacher)
        self.assertEqual(
            self.client.patch(review_url, {'correct': False}, format='json').status_code, 400
        )

    def test_activity_report_is_teacher_only(self):
        """Return aggregate activity to teachers and deny students."""

        Attempt.objects.create(
            student=self.student, question_item=self.question, submitted_answer='42'
        )
        url = reverse('activity-report') + f'?student={self.student.pk}&skill=two_digit_addition'
        self.client.force_authenticate(user=self.student_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['attempts'], 1)
        self.assertIsNone(response.data['correct_percentage'])

    def test_health_reports_database_state(self):
        """Return 200 for a live database and 503 when the check fails."""

        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(reverse('health')).status_code, 200)
        with patch('practice.views.HealthService.database_is_ready', return_value=False):
            self.assertEqual(self.client.get(reverse('health')).status_code, 503)
