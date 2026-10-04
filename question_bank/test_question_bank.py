"""Pytest coverage for question import, selection, and demonstration data."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Student
from practice.models import Attempt
from question_bank.exception import NoAvailableQuestion
from question_bank.models import (
    QuestionItem, RESPONSE_TYPE_CHOICES, ResponseType, Skill,
    VALIDATION_STATUS_CHOICES, ValidationStatus,
)
from question_bank.serializers import QuestionImportSerializer
from question_bank.services.import_questions import QuestionImportService
from question_bank.services.question_selector import QuestionSelectorService

pytestmark = pytest.mark.django_db


def test_integer_enums_define_model_field_choices():
    """Expose numeric enum codes and readable labels on the model fields.

    Input: Response-type and validation-status enum members.
    Output: Integer choice values and readable labels on both model fields.
    """

    assert ResponseType.SHORT_TEXT.value == 3
    assert ValidationStatus.ACCEPTED.value == 1
    assert RESPONSE_TYPE_CHOICES == [
        (1, 'Integer'), (2, 'Decimal'),
        (3, 'Short text'), (4, 'Multiple choice'),
    ]
    assert VALIDATION_STATUS_CHOICES == [
        (1, 'Accepted'), (2, 'Rejected'), (3, 'Flagged'),
    ]
    assert QuestionItem._meta.get_field('response_type').choices == RESPONSE_TYPE_CHOICES
    assert QuestionItem._meta.get_field('validation_status').choices == VALIDATION_STATUS_CHOICES


def test_import_serializer_accepts_numeric_codes(question_data):
    """Pass valid numeric choice codes through import validation.

    Input: A question payload with integer response and status codes.
    Output: Valid serializer data containing the same integer codes.
    """

    serializer = QuestionImportSerializer(data=question_data('q1', 'What is 1 + 1?'))
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['response_type'] == ResponseType.INTEGER.value
    assert serializer.validated_data['validation_status'] == ValidationStatus.ACCEPTED.value


def test_serializer_rejects_invalid_enum(question_data):
    """Reject an upstream response type outside the allowed choices.

    Input: A valid question payload with ``response_type`` set to ``banana``.
    Output: Invalid serializer with a ``response_type`` field error.
    """

    data = question_data('q1', 'What is 1 + 1?')
    data['response_type'] = 'banana'
    serializer = QuestionImportSerializer(data=data)
    assert not serializer.is_valid()
    assert 'response_type' in serializer.errors


def test_import_preserves_statuses_and_reports_bad_items(addition_skill, question_data):
    """Keep valid items while reporting each invalid batch neighbor.

    Input: Accepted, rejected, flagged, invalid-enum, unknown-skill, and
    wrong-grade question payloads.
    Output: Three saved statuses and three per-item errors.
    """

    bad_enum = question_data('bad', 'Invalid type?')
    bad_enum['response_type'] = 'banana'
    result = QuestionImportService.import_batch([
        question_data('q1', 'Accepted question?'),
        question_data('q2', 'Rejected question?', status=ValidationStatus.REJECTED.value),
        question_data('q3', 'Flagged question?', status=ValidationStatus.FLAGGED.value),
        bad_enum,
        question_data('unknown', 'Unknown skill?', skill='missing'),
        question_data('wrong-grade', 'Wrong grade?', grade=4),
    ])
    assert result['created'] == ['q1', 'q2', 'q3']
    assert len(result['errors']) == 3
    assert set(QuestionItem.objects.values_list('validation_status', flat=True)) == {
        ValidationStatus.ACCEPTED.value,
        ValidationStatus.REJECTED.value,
        ValidationStatus.FLAGGED.value,
    }
    assert QuestionItem.objects.get(pk='q1').response_type == ResponseType.INTEGER.value


def test_import_rejects_normalized_duplicates(addition_skill, question_data):
    """Reject prompts equal after whitespace and case normalization.

    Input: Three prompt variants across two imports with different IDs.
    Output: Only the first ID is saved and both later items report errors.
    """

    first = QuestionImportService.import_batch([
        question_data('q1', 'What is 10 + 20?'),
        question_data('q2', '  WHAT IS 10 + 20?  '),
    ])
    second = QuestionImportService.import_batch([
        question_data('q3', 'what is 10 + 20?'),
    ])
    assert first['created'] == ['q1']
    assert len(first['errors']) == 1
    assert len(second['errors']) == 1


def test_selector_excludes_rejected_and_recent_questions(
    addition_skill, fraction_skill, student_profile, question_data,
):
    """Select only an accepted, same-skill, not-recently-attempted item.

    Input: Two accepted addition items, one rejected item, another skill, and
    an attempt on the first addition item.
    Output: The second item, then ``NoAvailableQuestion`` after it is flagged.
    """

    QuestionImportService.import_batch([
        question_data('q1', 'First accepted?'),
        question_data('q2', 'Second accepted?'),
        question_data('q3', 'Rejected?', status=ValidationStatus.REJECTED.value),
        question_data('q4', 'Other skill?', skill=fraction_skill.slug),
    ])
    Attempt.objects.create(
        student=student_profile, question_item=QuestionItem.objects.get(pk='q1'),
        submitted_answer='answer',
    )
    selected = QuestionSelectorService.select_next(student_profile, addition_skill.slug)
    assert selected.pk == 'q2'

    QuestionItem.objects.filter(pk='q2').update(validation_status=ValidationStatus.FLAGGED.value)
    with pytest.raises(NoAvailableQuestion):
        QuestionSelectorService.select_next(student_profile, addition_skill.slug)


def test_selector_excludes_exactly_the_last_five_attempts(
    addition_skill, student_profile, question_data,
):
    """Make the oldest of six attempts eligible again.

    Input: Seven accepted questions, attempts on the first six, and a skill
    whose grade differs from the student's grade.
    Output: Question one is selected; the mismatched grade raises an error.
    """

    QuestionImportService.import_batch([
        question_data(f'q{number}', f'Question {number}?')
        for number in range(1, 8)
    ])
    for number in range(1, 7):
        Attempt.objects.create(
            student=student_profile,
            question_item=QuestionItem.objects.get(pk=f'q{number}'),
            submitted_answer='answer',
        )
    selected = QuestionSelectorService.select_next(student_profile, addition_skill.slug)
    assert selected.pk == 'q1'

    Skill.objects.create(
        slug='grade_four', name='Grade four', grade=4,
        learning_objective='Fourth grade skill.',
    )
    with pytest.raises(NoAvailableQuestion):
        QuestionSelectorService.select_next(student_profile, 'grade_four')


def test_import_requires_teacher_permission(
    api_client, addition_skill, student_user, teacher_user, question_data,
):
    """Allow teacher batch import and deny the same student request.

    Input: One valid and one invalid question sent by each role.
    Output: Student gets HTTP 403; teacher gets HTTP 200 with one created ID
    and one per-item error.
    """

    url = reverse('question-import')
    invalid = question_data('bad', 'Invalid item?')
    invalid['response_type'] = 'banana'
    payload = [question_data('q1', 'Question one?'), invalid]

    api_client.force_authenticate(user=student_user)
    assert api_client.post(url, payload, format='json').status_code == 403
    api_client.force_authenticate(user=teacher_user)
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 200
    assert response.data['created'] == ['q1']
    assert response.data['errors'][0]['id'] == 'bad'


def test_seed_creates_required_records_once():
    """Keep the demonstration seed idempotent and its dataset complete.

    Input: Two runs of ``seed_demo`` with the same password.
    Output: Two skills, fifteen questions, three students, three attempts,
    and ten accepted questions without duplicates.
    """

    output = StringIO()
    call_command('seed_demo', password='safe-pass-123', stdout=output)
    call_command('seed_demo', password='safe-pass-123', stdout=output)
    assert Skill.objects.count() == 2
    assert QuestionItem.objects.count() == 15
    assert Student.objects.count() == 3
    assert Attempt.objects.count() == 3
    assert QuestionItem.objects.filter(validation_status=ValidationStatus.ACCEPTED.value).count() == 10
