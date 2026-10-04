"""Student practice, teacher review, reporting, and health endpoints."""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Student
from accounts.permissions import IsStudent, IsTeacher
from practice.exception import PracticeInputError
from practice.serializers import (
    ActivityQuerySerializer, AttemptSerializer, AttemptSubmitSerializer, ReviewSerializer,
)
from practice.services.attempts import AttemptService
from practice.services.health import HealthService
from practice.services.reports import ActivityReportService
from question_bank.serializers import PracticeQuestionSerializer
from question_bank.services.question_selector import QuestionSelectorService


class NextQuestionView(APIView):
    """Serve the next eligible question to a student.

    GET ``/api/practice/next/?skill=<slug>`` requires student-group membership
    and ``view_questionitem`` permission. Selection happens in the dedicated
    service, which applies skill, grade, status, and recent-attempt rules.
    """

    permission_classes = [IsStudent]
    required_permission = 'question_bank.view_questionitem'

    def get(self, request):
        """Validate the skill query and return one learner-facing question.

        Args:
            request: Authenticated DRF request with a ``skill`` query value.

        Returns:
            HTTP 200 with question ID, skill, grade, prompt, and response type.

        Raises:
            PracticeInputError: If the skill value or student profile is absent.
            NoAvailableQuestion: If the selection service finds no candidate.
        """

        skill = request.query_params.get('skill')
        if not skill:
            raise PracticeInputError('A skill query parameter is required.')
        student = Student.objects.filter(user=request.user).first()
        if student is None:
            raise PracticeInputError('Student profile is missing.')
        question = QuestionSelectorService.select_next(student, skill)
        return Response(PracticeQuestionSerializer(question).data)


class AttemptSubmitView(APIView):
    """Accept student answers without deciding correctness.

    POST ``/api/attempts/`` requires the student group and ``add_attempt``
    permission. Review fields are controlled by the service, not request data.
    """

    permission_classes = [IsStudent]
    required_permission = 'practice.add_attempt'

    def post(self, request):
        """Validate an answer and create a pending attempt.

        Args:
            request: Authenticated DRF request with question ID, answer text,
                and optional time spent.

        Returns:
            HTTP 201 with the saved attempt and null review fields.

        Raises:
            PracticeInputError: For malformed input, a missing profile, or a
                question unavailable to the student.
        """

        serializer = AttemptSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            raise PracticeInputError(serializer.errors)
        student = Student.objects.filter(user=request.user).first()
        if student is None:
            raise PracticeInputError('Student profile is missing.')
        attempt = AttemptService.submit(student, serializer.validated_data)
        return Response(AttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class PendingAttemptsView(APIView):
    """Show teachers the queue of unreviewed student attempts.

    GET ``/api/attempts/pending/`` requires the teacher group and
    ``view_attempt`` permission. Already reviewed attempts are excluded.
    """

    permission_classes = [IsTeacher]
    required_permission = 'practice.view_attempt'

    def get(self, request):
        """Serialize pending attempts from oldest to newest.

        Args:
            request: Authenticated teacher's DRF request.

        Returns:
            HTTP 200 with an array of attempts, including submitted answers.
        """

        return Response(AttemptSerializer(AttemptService.pending(), many=True).data)


class ReviewAttemptView(APIView):
    """Record a teacher's decision on one pending attempt.

    PATCH ``/api/attempts/<id>/review/`` requires the teacher group and
    ``change_attempt`` permission. The service records the authenticated user
    as reviewer and rejects an attempt that already has a decision.
    """

    permission_classes = [IsTeacher]
    required_permission = 'practice.change_attempt'

    def patch(self, request, attempt_id):
        """Validate a decision and return the updated attempt.

        Args:
            request: Authenticated teacher request containing ``correct``.
            attempt_id: Attempt primary key from the URL.

        Returns:
            HTTP 200 with correctness and reviewer fields set.

        Raises:
            PracticeInputError: If ``correct`` is missing or malformed.
            AttemptNotFound: If the attempt ID is unknown.
            AttemptAlreadyReviewed: If the attempt was previously reviewed.
        """

        serializer = ReviewSerializer(data=request.data)
        if not serializer.is_valid():
            raise PracticeInputError(serializer.errors)
        attempt = AttemptService.review(
            attempt_id, request.user, serializer.validated_data['correct']
        )
        return Response(AttemptSerializer(attempt).data)


class ActivityReportView(APIView):
    """Give teachers an activity summary for one student and skill.

    GET ``/api/reports/activity/?student=<id>&skill=<slug>`` requires the
    teacher group and ``view_attempt`` permission. The service calculates all
    counts in the database rather than loading attempts into Python.
    """

    permission_classes = [IsTeacher]
    required_permission = 'practice.view_attempt'

    def get(self, request):
        """Return total, pending, and reviewed-only correctness metrics.

        Args:
            request: Authenticated teacher request with student and skill
                query parameters.

        Returns:
            HTTP 200 with total attempts, pending count, and a nullable
            correct percentage for the requested pair.

        Raises:
            PracticeInputError: For invalid filters or unknown records.
        """

        serializer = ActivityQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            raise PracticeInputError(serializer.errors)
        result = ActivityReportService.report(
            serializer.validated_data['student'], serializer.validated_data['skill']
        )
        return Response(result)


class HealthView(APIView):
    """Expose application/database readiness without authentication.

    GET ``/api/health/`` performs a small database query. This route can be
    used by an operator or container health check without a JWT.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        """Turn the database check into a health response.

        Args:
            request: Public DRF request; no credentials or body are required.

        Returns:
            HTTP 200 with ``status=ok`` when the database responds, or HTTP
            503 with ``status=unhealthy`` when it cannot be queried.
        """

        if HealthService.database_is_ready():
            return Response({'status': 'ok', 'database': 'ok'})
        return Response(
            {'status': 'unhealthy', 'database': 'unavailable'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
