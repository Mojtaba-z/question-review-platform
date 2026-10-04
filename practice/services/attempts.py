"""Submission and teacher-review business operations."""

from django.db import transaction

from practice.exception import AttemptAlreadyReviewed, AttemptNotFound, PracticeInputError
from practice.models import Attempt
from question_bank.models import QuestionItem, ValidationStatus


class AttemptService:
    """Own the state changes in the student-answer workflow.

    Submission checks that the question is accepted and matches the student's
    grade, then creates a pending attempt. Review locks one pending attempt,
    records a teacher's True/False decision, and prevents a second review.
    """

    @staticmethod
    def submit(student, data):
        """Create a pending attempt for an eligible question.

        Args:
            student: Authenticated user's saved ``Student`` profile.
            data: Serializer-validated question ID, answer text, and optional
                time spent in seconds.

        Returns:
            A saved ``Attempt`` with ``reviewed_correct`` and ``reviewed_by``
            both set to None. The answer is never graded here.

        Raises:
            PracticeInputError: If the question is missing, not accepted, or
                intended for a different grade.
        """

        question = QuestionItem.objects.filter(pk=data['question_item']).first()
        if (
            question is None
            or question.validation_status != ValidationStatus.ACCEPTED
            or question.grade != student.grade
        ):
            raise PracticeInputError('This question is not available to the student.')

        return Attempt.objects.create(
            student=student,
            question_item=question,
            submitted_answer=data['submitted_answer'],
            time_spent_seconds=data.get('time_spent_seconds'),
            reviewed_correct=None,
            reviewed_by=None,
        )

    @staticmethod
    def pending():
        """Build the teacher's queue of unanswered review decisions.

        Returns:
            An unevaluated queryset with ``reviewed_correct=None``, ordered
            by creation time and ID from oldest to newest.
        """

        return Attempt.objects.filter(reviewed_correct__isnull=True).order_by('created_at', 'pk')

    @staticmethod
    @transaction.atomic
    def review(attempt_id, reviewer, correct):
        """Store one teacher decision on a pending attempt.

        A database row lock and transaction prevent concurrent reviewers from
        both accepting the same pending attempt. A False decision is reviewed,
        just as a True decision is; only None is still pending.

        Args:
            attempt_id: Primary key of the attempt being reviewed.
            reviewer: Authenticated teacher user to record as ``reviewed_by``.
            correct: Teacher's boolean correctness decision.

        Returns:
            The updated ``Attempt`` with its decision and reviewer saved.

        Raises:
            AttemptNotFound: If the ID has no matching attempt.
            AttemptAlreadyReviewed: If a decision already exists.
        """

        attempt = Attempt.objects.select_for_update().filter(pk=attempt_id).first()
        if attempt is None:
            raise AttemptNotFound()
        if attempt.reviewed_correct is not None:
            raise AttemptAlreadyReviewed()

        attempt.reviewed_correct = correct
        attempt.reviewed_by = reviewer
        attempt.save(update_fields=['reviewed_correct', 'reviewed_by', 'updated_at'])
        return attempt
