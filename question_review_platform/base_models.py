from django.db import models


class BaseModel(models.Model):
    """Supply timestamps to concrete domain models without creating a table.

    ``created_at`` is set on insertion, and ``updated_at`` changes on saves.
    Student, Skill, QuestionItem, and Attempt inherit these fields so their
    records can be ordered or audited by time.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Make timestamp fields inherit without a separate base-model table."""

        abstract = True
