from django.conf import settings
from django.db import models

from question_review_platform.base_models import BaseModel


class Student(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='students',
    )
    grade = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return f'{self.user} (grade {self.grade})'
