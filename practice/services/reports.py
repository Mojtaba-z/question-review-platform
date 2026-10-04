"""Database-backed student activity reporting."""

from django.db.models import Count, Q

from accounts.models import Student
from practice.exception import PracticeInputError
from practice.models import Attempt
from question_bank.models import Skill


class ActivityReportService:
    """Calculate student activity from database aggregates.

    The percentage uses reviewed attempts only as its denominator. Pending
    attempts count toward total activity but do not affect correctness.
    """

    @staticmethod
    def report(student_id, skill_slug):
        """Report one student's attempts for one existing skill.

        Args:
            student_id: Primary key of a ``Student`` profile.
            skill_slug: Primary key of the skill to group attempts by.

        Returns:
            A mapping with student and skill identifiers, total attempts,
            pending attempts, and correct percentage among reviewed attempts.
            The percentage is None when no attempts have been reviewed.

        Raises:
            PracticeInputError: If the student or skill does not exist.
        """

        if not Student.objects.filter(pk=student_id).exists():
            raise PracticeInputError('Unknown student.')
        if not Skill.objects.filter(pk=skill_slug).exists():
            raise PracticeInputError('Unknown skill.')

        counts = Attempt.objects.filter(
            student_id=student_id, question_item__skill_id=skill_slug
        ).aggregate(
            attempts=Count('id'),
            pending=Count('id', filter=Q(reviewed_correct__isnull=True)),
            correct=Count('id', filter=Q(reviewed_correct=True)),
        )
        reviewed = counts['attempts'] - counts['pending']
        percentage = None if reviewed == 0 else 100 * counts['correct'] / reviewed
        return {
            'student': student_id,
            'skill': skill_slug,
            'attempts': counts['attempts'],
            'pending': counts['pending'],
            'correct_percentage': percentage,
        }
