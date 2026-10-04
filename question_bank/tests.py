"""Unit and HTTP tests for question import and selection."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.constants import STUDENT_GROUP, TEACHER_GROUP
from accounts.models import Student
from accounts.services.roles import RoleService
from question_bank.exception import NoAvailableQuestion
from question_bank.models import QuestionItem, Skill, ValidationStatus
from question_bank.serializers import QuestionImportSerializer
from question_bank.services.import_questions import QuestionImportService
from question_bank.services.question_selector import QuestionSelectorService


def question_data(item_id, prompt, status='accepted', skill='two_digit_addition', grade=3):
    """Return one valid upstream item for service and endpoint tests."""

    return {
        'id': item_id,
        'skill': skill,
        'grade': grade,
        'prompt_en': prompt,
        'response_type': 'integer',
        'requested_difficulty': 2,
        'assessed_difficulty': 2,
        'source_question_ids': ['wk_001'],
        'generation_config': {'prompt_version': 'test'},
        'validation_status': status,
        'validation_reasons': ['schema_ok'],
    }


class QuestionServiceTests(TestCase):
    """Test import validation, duplicate detection, and practice selection."""

    def setUp(self):
        """Create skills and a student used by each service test."""

        self.skill = Skill.objects.create(
            slug='two_digit_addition', name='Addition', grade=3,
            learning_objective='Add numbers.',
        )
        Skill.objects.create(
            slug='simple_fractions', name='Fractions', grade=3,
            learning_objective='Identify fractions.',
        )
        user = get_user_model().objects.create_user('student', password='safe-pass-123')
        self.student = Student.objects.create(user=user, grade=3)

    def test_serializer_rejects_invalid_enum(self):
        """Reject an upstream response type outside the contract."""

        data = question_data('q1', 'What is 1 + 1?')
        data['response_type'] = 'banana'
        serializer = QuestionImportSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('response_type', serializer.errors)

    def test_import_preserves_statuses_and_reports_bad_items(self):
        """Persist accepted, rejected, and flagged items with per-item errors."""

        bad_enum = question_data('bad', 'Invalid type?')
        bad_enum['response_type'] = 'banana'
        result = QuestionImportService.import_batch([
            question_data('q1', 'Accepted question?'),
            question_data('q2', 'Rejected question?', 'rejected'),
            question_data('q3', 'Flagged question?', 'flagged'),
            bad_enum,
            question_data('unknown', 'Unknown skill?', skill='missing'),
            question_data('wrong-grade', 'Wrong grade?', grade=4),
        ])
        self.assertEqual(result['created'], ['q1', 'q2', 'q3'])
        self.assertEqual(len(result['errors']), 3)
        self.assertEqual(
            set(QuestionItem.objects.values_list('validation_status', flat=True)),
            {'accepted', 'rejected', 'flagged'},
        )

    def test_import_rejects_normalized_duplicates(self):
        """Reject repeated prompts inside a batch and against stored records."""

        first = QuestionImportService.import_batch([
            question_data('q1', 'What is 10 + 20?'),
            question_data('q2', '  WHAT IS 10 + 20?  '),
        ])
        second = QuestionImportService.import_batch([
            question_data('q3', 'what is 10 + 20?')
        ])
        self.assertEqual(first['created'], ['q1'])
        self.assertEqual(len(first['errors']), 1)
        self.assertEqual(len(second['errors']), 1)

    def test_selector_excludes_rejected_and_recent_questions(self):
        """Select accepted same-skill and same-grade questions not recently attempted."""

        from practice.models import Attempt

        QuestionImportService.import_batch([
            question_data('q1', 'First accepted?'),
            question_data('q2', 'Second accepted?'),
            question_data('q3', 'Rejected?', 'rejected'),
            question_data('q4', 'Other skill?', skill='simple_fractions'),
        ])
        Attempt.objects.create(
            student=self.student, question_item=QuestionItem.objects.get(pk='q1'),
            submitted_answer='answer',
        )
        selected = QuestionSelectorService.select_next(self.student, self.skill.slug)
        self.assertEqual(selected.pk, 'q2')
        QuestionItem.objects.filter(pk='q2').update(validation_status=ValidationStatus.FLAGGED)
        with self.assertRaises(NoAvailableQuestion):
            QuestionSelectorService.select_next(self.student, self.skill.slug)

    def test_selector_excludes_exactly_the_last_five_attempts(self):
        """Allow a question outside the five most recent attempts again."""

        from practice.models import Attempt

        QuestionImportService.import_batch([
            question_data(f'q{number}', f'Question {number}?')
            for number in range(1, 8)
        ])
        for number in range(1, 7):
            Attempt.objects.create(
                student=self.student,
                question_item=QuestionItem.objects.get(pk=f'q{number}'),
                submitted_answer='answer',
            )
        selected = QuestionSelectorService.select_next(self.student, self.skill.slug)
        self.assertEqual(selected.pk, 'q1')

        Skill.objects.create(
            slug='grade_four', name='Grade four', grade=4,
            learning_objective='Fourth grade skill.',
        )
        with self.assertRaises(NoAvailableQuestion):
            QuestionSelectorService.select_next(self.student, 'grade_four')


class QuestionImportEndpointTests(APITestCase):
    """Check teacher-only question import over HTTP."""

    def setUp(self):
        """Create a skill and users in the student and teacher groups."""

        Skill.objects.create(
            slug='two_digit_addition', name='Addition', grade=3,
            learning_objective='Add numbers.',
        )
        user_model = get_user_model()
        self.teacher = user_model.objects.create_user('teacher', password='safe-pass-123')
        self.student = user_model.objects.create_user('student', password='safe-pass-123')
        RoleService.assign_role(self.teacher, TEACHER_GROUP)
        RoleService.assign_role(self.student, STUDENT_GROUP)

    def test_import_requires_teacher_permission(self):
        """Return 403 to a student and per-item results to a teacher."""

        url = reverse('question-import')
        invalid = question_data('bad', 'Invalid item?')
        invalid['response_type'] = 'banana'
        payload = [question_data('q1', 'Question one?'), invalid]
        self.client.force_authenticate(user=self.student)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 403)
        self.client.force_authenticate(user=self.teacher)
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], ['q1'])
        self.assertEqual(response.data['errors'][0]['id'], 'bad')


class SeedCommandTests(TestCase):
    """Check that sample data is complete and repeatable."""

    def test_seed_creates_required_records_once(self):
        """Create two skills, fifteen questions, users, and mixed attempts."""

        from practice.models import Attempt

        output = StringIO()
        call_command('seed_demo', password='safe-pass-123', stdout=output)
        call_command('seed_demo', password='safe-pass-123', stdout=output)
        self.assertEqual(Skill.objects.count(), 2)
        self.assertEqual(QuestionItem.objects.count(), 15)
        self.assertEqual(Student.objects.count(), 3)
        self.assertEqual(Attempt.objects.count(), 3)
        self.assertEqual(
            QuestionItem.objects.filter(validation_status=ValidationStatus.ACCEPTED).count(), 10
        )
