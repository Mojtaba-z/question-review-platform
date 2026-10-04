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
        """Define database rules for student profiles.

        The unique user constraint prevents duplicate profiles for one
        account. The grade index supports lookups by school grade.
        """

        constraints = [models.UniqueConstraint(fields=['user'], name='one_student_per_user')]
        indexes = [models.Index(fields=['grade'], name='student_grade_idx')]

    def __str__(self):
        """Return a readable profile label for logs and Django admin.

        The value combines the related user's display string with this
        profile's grade, such as ``alice (grade 3)``.
        """

        return f'{self.user} (grade {self.grade})'
