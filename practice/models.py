from django.conf import settings
from django.db import models

from question_review_platform.base_models import BaseModel


class Attempt(BaseModel):
    """Record one student's response to one imported question.

    ``reviewed_correct`` starts as ``None`` and remains pending until a teacher
    sets it to True or False. The reviewing user is stored separately. There
    is no answer key or automatic correctness calculation; multiple attempts
    by the same student on a question are allowed.
    """

    student = models.ForeignKey(
        'accounts.Student', on_delete=models.CASCADE, related_name='attempts'
    )
    question_item = models.ForeignKey(
        'question_bank.QuestionItem', on_delete=models.PROTECT, related_name='attempts'
    )
    submitted_answer = models.TextField()
    reviewed_correct = models.BooleanField(null=True, default=None)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_attempts',
    )
    time_spent_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        """Define indexes for practice selection and the review queue.

        Student and descending creation time help find recent attempts. Review
        state and creation time help list pending submissions for teachers.
        """

        indexes = [
            models.Index(fields=['student', '-created_at'], name='attempt_recent_idx'),
            models.Index(fields=['reviewed_correct', 'created_at'], name='attempt_review_idx'),
        ]

    def __str__(self):
        """Return a compact label for an attempt.

        The label combines the student profile ID and upstream question ID so
        logs and Django admin can identify the linked records.
        """

        return f'{self.student_id}: {self.question_item_id}'
