"""Shared pytest fixtures for account, question, and practice tests."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.constants import STUDENT_GROUP, TEACHER_GROUP
from accounts.models import Student
from accounts.services.roles import RoleService
from question_bank.models import QuestionItem, ResponseType, Skill, ValidationStatus
from question_bank.services.import_questions import QuestionImportService


@pytest.fixture
def api_client():
    """Provide a fresh DRF client for one test.

    Input: No setup data.
    Output: An unauthenticated ``APIClient`` instance.
    """

    return APIClient()


@pytest.fixture
def addition_skill(db):
    """Create the grade-three addition skill used by question fixtures.

    Input: An isolated pytest database.
    Output: The saved ``Skill`` instance.
    """

    return Skill.objects.create(
        slug='two_digit_addition', name='Addition', grade=3,
        learning_objective='Add numbers.',
    )


@pytest.fixture
def fraction_skill(db):
    """Create a second grade-three skill for selection tests.

    Input: An isolated pytest database.
    Output: The saved fractions ``Skill`` instance.
    """

    return Skill.objects.create(
        slug='simple_fractions', name='Fractions', grade=3,
        learning_objective='Identify fractions.',
    )


@pytest.fixture
def student_user(db):
    """Create a user with the student group and its permissions.

    Input: An isolated pytest database.
    Output: The saved Django user; a profile is created separately if needed.
    """

    user = get_user_model().objects.create_user('student', password='safe-pass-123')
    RoleService.assign_role(user, STUDENT_GROUP)
    return user


@pytest.fixture
def student_profile(student_user):
    """Create a grade-three profile for the shared student user.

    Input: ``student_user`` from its fixture.
    Output: The saved ``Student`` profile.
    """

    return Student.objects.create(user=student_user, grade=3)


@pytest.fixture
def teacher_user(db):
    """Create a user with the teacher group and its permissions.

    Input: An isolated pytest database.
    Output: The saved Django user.
    """

    user = get_user_model().objects.create_user('teacher', password='safe-pass-123')
    RoleService.assign_role(user, TEACHER_GROUP)
    return user


@pytest.fixture
def question_data():
    """Provide a builder for complete upstream question payloads.

    Input: No database state.
    Output: A callable that accepts ID, prompt, status, skill, and grade.
    """

    def build(
        item_id, prompt, status=ValidationStatus.ACCEPTED.value,
        skill='two_digit_addition', grade=3,
    ):
        """Build one valid import payload with caller-selected fields.

        Input: Upstream ID, prompt, and optional status, skill slug, and grade.
        Output: A dictionary matching the question import contract.
        """

        return {
            'id': item_id,
            'skill': skill,
            'grade': grade,
            'prompt_en': prompt,
            'response_type': ResponseType.INTEGER.value,
            'requested_difficulty': 2,
            'assessed_difficulty': 2,
            'source_question_ids': ['wk_001'],
            'generation_config': {'prompt_version': 'test'},
            'validation_status': status,
            'validation_reasons': ['schema_ok'],
        }

    return build


@pytest.fixture
def question_factory(addition_skill, question_data):
    """Provide a small factory that imports real question records.

    Input: The addition skill and question payload builder.
    Output: A callable that returns a saved ``QuestionItem`` for an ID.
    """

    def create(item_id, status=ValidationStatus.ACCEPTED.value):
        """Import one grade-three addition question for test setup.

        Input: Upstream ID and optional validation status.
        Output: The saved ``QuestionItem``; setup errors fail the test.
        """

        payload = question_data(item_id, f'What is {item_id} plus one?', status=status)
        result = QuestionImportService.import_batch([payload])
        assert result['errors'] == []
        return QuestionItem.objects.get(pk=item_id)

    return create
