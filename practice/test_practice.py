"""Pytest coverage for practice, review, reports, and health."""

from unittest.mock import patch

import pytest
from django.urls import reverse

from practice.exception import AttemptAlreadyReviewed, PracticeInputError
from practice.models import Attempt
from practice.serializers import ActivityQuerySerializer, AttemptSubmitSerializer, ReviewSerializer
from practice.services.attempts import AttemptService
from practice.services.reports import ActivityReportService
from question_bank.models import QuestionItem, ResponseType, ValidationStatus

pytestmark = pytest.mark.django_db


def test_submission_serializer_and_pending_service(student_profile, question_factory):
    """Save an eligible response pending review and reject an ineligible one.

    Input: Valid answer for an accepted item, then an answer for a rejected item.
    Output: Pending attempt with timing, then ``PracticeInputError``.
    """

    accepted = question_factory('q1')
    rejected = question_factory('q2', status=ValidationStatus.REJECTED.value)
    serializer = AttemptSubmitSerializer(data={
        'question_item': accepted.pk,
        'submitted_answer': '42',
        'time_spent_seconds': 20,
    })
    assert serializer.is_valid()
    attempt = AttemptService.submit(student_profile, serializer.validated_data)
    assert attempt.reviewed_correct is None
    assert attempt.reviewed_by is None
    assert attempt.time_spent_seconds == 20

    with pytest.raises(PracticeInputError):
        AttemptService.submit(student_profile, {
            'question_item': rejected.pk, 'submitted_answer': '42',
        })


def test_serializers_reject_missing_or_invalid_inputs():
    """Reject malformed submission, review, and report values.

    Input: Missing answer, nonboolean review decision, and invalid report filters.
    Output: All three serializers report invalid input.
    """

    assert not AttemptSubmitSerializer(data={'question_item': 'q1'}).is_valid()
    assert not ReviewSerializer(data={'correct': 'maybe'}).is_valid()
    assert not ActivityQuerySerializer(data={'student': -1}).is_valid()


def test_review_sets_reviewer_and_rejects_repeat(
    student_profile, teacher_user, question_factory,
):
    """Record one false review and refuse to overwrite it.

    Input: Pending attempt, teacher, False decision, then a True decision.
    Output: Teacher and False persist; the second review raises
    ``AttemptAlreadyReviewed``.
    """

    accepted = question_factory('q1')
    attempt = Attempt.objects.create(
        student=student_profile, question_item=accepted, submitted_answer='42',
    )
    review = ReviewSerializer(data={'correct': False})
    assert review.is_valid()
    reviewed = AttemptService.review(attempt.pk, teacher_user, review.validated_data['correct'])
    assert reviewed.reviewed_correct is False
    assert reviewed.reviewed_by == teacher_user

    with pytest.raises(AttemptAlreadyReviewed):
        AttemptService.review(attempt.pk, teacher_user, True)


def test_report_uses_reviewed_attempts_as_denominator(student_profile, question_factory):
    """Exclude pending answers from the correctness denominator.

    Input: One correct, one incorrect, and one pending attempt for one skill.
    Output: Three attempts, one pending, and 50 percent correct.
    """

    accepted = question_factory('q1')
    for answer, correctness in [('a', True), ('b', False), ('c', None)]:
        Attempt.objects.create(
            student=student_profile, question_item=accepted,
            submitted_answer=answer, reviewed_correct=correctness,
        )
    report = ActivityReportService.report(student_profile.pk, 'two_digit_addition')
    assert report['attempts'] == 3
    assert report['pending'] == 1
    assert report['correct_percentage'] == 50.0


def test_next_question_is_student_only(
    api_client, student_profile, teacher_user, question_factory,
):
    """Return an eligible question only to a student.

    Input: The same queue GET from student and teacher users.
    Output: Student gets HTTP 200 with question ``q1`` and its response type
    enum name; teacher gets HTTP 403.
    """

    question_factory('q1')
    url = reverse('practice-next') + '?skill=two_digit_addition'
    api_client.force_authenticate(user=student_profile.user)
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.data['id'] == 'q1'
    assert response.data['response_type'] == ResponseType.INTEGER.name

    api_client.force_authenticate(user=teacher_user)
    assert api_client.get(url).status_code == 403


def test_next_question_reports_no_eligible_item(
    api_client, student_profile, question_factory,
):
    """Report an empty queue when the sole question is flagged.

    Input: Student queue GET after changing the only item to flagged.
    Output: HTTP 404 with no ineligible question exposed.
    """

    question = question_factory('q1')
    QuestionItem.objects.filter(pk=question.pk).update(
        validation_status=ValidationStatus.FLAGGED.value
    )
    api_client.force_authenticate(user=student_profile.user)
    response = api_client.get(reverse('practice-next') + '?skill=two_digit_addition')
    assert response.status_code == 404


def test_login_jwt_opens_student_endpoint(api_client, student_profile, question_factory):
    """Use a real login JWT on a protected practice route.

    Input: Student credentials, then bearer access token on the queue GET.
    Output: HTTP 200 login and HTTP 200 question response with ID ``q1``.
    """

    question_factory('q1')
    login = api_client.post(reverse('login'), {
        'username': 'student', 'password': 'safe-pass-123',
    }, format='json')
    assert login.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')
    response = api_client.get(reverse('practice-next') + '?skill=two_digit_addition')
    assert response.status_code == 200
    assert response.data['id'] == 'q1'


def test_submit_is_student_only_and_remains_pending(
    api_client, student_profile, teacher_user, question_factory,
):
    """Create a pending answer through the student API only.

    Input: The same answer POST from student and teacher users.
    Output: Student gets HTTP 201 with empty review fields; teacher gets 403.
    """

    question_factory('q1')
    url = reverse('attempt-submit')
    body = {'question_item': 'q1', 'submitted_answer': '42'}
    api_client.force_authenticate(user=student_profile.user)
    response = api_client.post(url, body, format='json')
    assert response.status_code == 201
    assert response.data['reviewed_correct'] is None
    assert response.data['reviewed_by'] is None

    api_client.force_authenticate(user=teacher_user)
    assert api_client.post(url, body, format='json').status_code == 403


def test_pending_and_review_are_teacher_only(
    api_client, student_profile, teacher_user, question_factory,
):
    """Limit pending-list and review operations to teachers.

    Input: Student and teacher requests around one pending attempt.
    Output: Student gets HTTP 403; teacher lists it, marks it correct, and
    receives HTTP 400 when attempting a second review.
    """

    question = question_factory('q1')
    attempt = Attempt.objects.create(
        student=student_profile, question_item=question, submitted_answer='42',
    )
    list_url = reverse('attempts-pending')
    review_url = reverse('attempt-review', args=[attempt.pk])

    api_client.force_authenticate(user=student_profile.user)
    assert api_client.get(list_url).status_code == 403
    assert api_client.patch(review_url, {'correct': True}, format='json').status_code == 403

    api_client.force_authenticate(user=teacher_user)
    assert len(api_client.get(list_url).data) == 1
    response = api_client.patch(review_url, {'correct': True}, format='json')
    assert response.status_code == 200
    attempt.refresh_from_db()
    assert attempt.reviewed_correct is True
    assert attempt.reviewed_by == teacher_user
    assert api_client.patch(review_url, {'correct': False}, format='json').status_code == 400


def test_activity_report_is_teacher_only(
    api_client, student_profile, teacher_user, question_factory,
):
    """Return a pending-only activity report only to teachers.

    Input: One pending attempt and report GETs from student and teacher.
    Output: HTTP 403 for student; HTTP 200, one attempt, and null correctness
    percentage for teacher.
    """

    question = question_factory('q1')
    Attempt.objects.create(
        student=student_profile, question_item=question, submitted_answer='42',
    )
    url = reverse('activity-report') + (
        f'?student={student_profile.pk}&skill=two_digit_addition'
    )
    api_client.force_authenticate(user=student_profile.user)
    assert api_client.get(url).status_code == 403

    api_client.force_authenticate(user=teacher_user)
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.data['attempts'] == 1
    assert response.data['correct_percentage'] is None


def test_health_reports_database_state(api_client):
    """Expose healthy and failed database probes through the public endpoint.

    Input: Health GET with a working database, then with a patched failed probe.
    Output: HTTP 200 followed by HTTP 503.
    """

    assert api_client.get(reverse('health')).status_code == 200
    with patch('practice.views.HealthService.database_is_ready', return_value=False):
        assert api_client.get(reverse('health')).status_code == 503
