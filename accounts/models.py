from django.conf import settings
from django.db import models

from question_review_platform.base_models import BaseModel


class Student(BaseModel):
    """Hold the school grade for a user who practices questions.

    Each user has at most one student profile, enforced by the database
    constraint below. Deleting the user deletes the profile. Practice selection
    compares this grade with both the skill and question grades.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='students',
    )
    grade = models.PositiveSmallIntegerField()

    class Meta:
        """Enforce one profile per user and support grade-based lookups."""

        constraints = [models.UniqueConstraint(fields=['user'], name='one_student_per_user')]
        indexes = [models.Index(fields=['grade'], name='student_grade_idx')]

    def __str__(self):
        """Return the user's display value followed by their grade."""

        return f'{self.user} (grade {self.grade})'
