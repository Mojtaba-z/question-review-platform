from django.db import models

from question_review_platform.base_models import BaseModel


class Skill(BaseModel):
    """Represent a named learning objective for one school grade.

    The slug is both the primary key and the identifier used by the upstream
    question contract and practice API. Questions refer to an existing skill;
    deleting a skill with questions is blocked by their protected foreign key.
    """

    slug = models.SlugField(primary_key=True)
    name = models.CharField(max_length=255)
    grade = models.PositiveSmallIntegerField(db_index=True)
    learning_objective = models.TextField()

    def __str__(self):
        """Return the name shown for this skill in Django admin and logs."""

        return self.name


class ResponseType(models.TextChoices):
    """Enumerate response formats permitted by the upstream JSON contract.

    This describes the expected shape of a student's response. It does not
    provide an answer key or enable automatic grading.
    """

    INTEGER = 'integer', 'Integer'
    DECIMAL = 'decimal', 'Decimal'
    SHORT_TEXT = 'short_text', 'Short text'
    MULTIPLE_CHOICE = 'multiple_choice', 'Multiple choice'


class ValidationStatus(models.TextChoices):
    """Enumerate the upstream labels preserved with each imported question.

    Import validation still runs locally. Only an item stored with ``accepted``
    status is eligible for the practice queue; rejected and flagged items remain
    in the database for traceability.
    """

    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    FLAGGED = 'flagged', 'Flagged'


class QuestionItem(BaseModel):
    """Store one upstream question and its generation/validation metadata.

    The upstream ``id`` remains the primary key. ``prompt_hash`` is an internal
    SHA-256 digest of the normalized prompt, used to reject exact normalized
    duplicates. The model intentionally has no answer, hint, or solution field;
    teachers decide whether submitted responses are correct.
    """

    id = models.CharField(max_length=255, primary_key=True)
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name='questions')
    grade = models.PositiveSmallIntegerField()
    prompt_en = models.TextField()
    prompt_hash = models.CharField(max_length=64, unique=True, editable=False)
    response_type = models.CharField(max_length=32, choices=ResponseType.choices)
    requested_difficulty = models.IntegerField()
    assessed_difficulty = models.IntegerField(null=True, blank=True)
    source_question_ids = models.JSONField()
    generation_config = models.JSONField()
    validation_status = models.CharField(max_length=16, choices=ValidationStatus.choices)
    validation_reasons = models.JSONField()

    class Meta:
        """Index skill, grade, and status filtering for practice selection."""

        indexes = [
            models.Index(
                fields=['skill', 'grade', 'validation_status'],
                name='question_selection_idx',
            ),
        ]

    def __str__(self):
        """Return the upstream identifier used in imports and API responses."""

        return self.pk
