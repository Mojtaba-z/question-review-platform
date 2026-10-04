"""Choose the next eligible question for a student."""

from question_bank.constants import RECENT_ATTEMPT_LIMIT
from question_bank.exception import NoAvailableQuestion
from question_bank.models import QuestionItem, Skill, ValidationStatus


class QuestionSelectorService:
    """Choose a practice item without embedding queue rules in a view.

    Candidates must be accepted, match the requested skill and student's
    grade, and not appear among that student's five most recent attempts.
    The lowest upstream ID is selected to make the policy deterministic.
    """

    @staticmethod
    def select_next(student, skill_slug):
        """Return the next question allowed by the practice queue policy.

        Args:
            student: Saved ``Student`` profile whose grade and attempts apply.
            skill_slug: Requested ``Skill`` primary key from the query string.

        Returns:
            The first eligible ``QuestionItem`` ordered by upstream ID.

        Raises:
            NoAvailableQuestion: If the skill is absent, its grade differs,
                or no accepted question remains after recent exclusions.
        """

        from practice.models import Attempt

        skill = Skill.objects.filter(slug=skill_slug, grade=student.grade).first()
        if skill is None:
            raise NoAvailableQuestion()

        recent_ids = list(
            Attempt.objects.filter(student=student)
            .order_by('-created_at', '-pk')
            .values_list('question_item_id', flat=True)[:RECENT_ATTEMPT_LIMIT]
        )
        question = (
            QuestionItem.objects.filter(
                skill=skill,
                grade=student.grade,
                validation_status=ValidationStatus.ACCEPTED,
            )
            .exclude(pk__in=recent_ids)
            .order_by('id')
            .first()
        )
        if question is None:
            raise NoAvailableQuestion()
        return question
