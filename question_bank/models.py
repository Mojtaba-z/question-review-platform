from enum import IntEnum

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
        """Return the human-readable name for this skill.

        Django admin and logs display this name when they represent a skill
        as text; its slug remains the identifier used by APIs and relations.
        """

        return self.name


class ResponseType(IntEnum):
    """Enumerate response formats permitted by the upstream JSON contract.

    This describes the expected shape of a student's response. It does not
    provide an answer key or enable automatic grading.
    """

    INTEGER = 1
    DECIMAL = 2
    SHORT_TEXT = 3
    MULTIPLE_CHOICE = 4


class ValidationStatus(IntEnum):
    """Enumerate the numeric validation codes stored with each question.

    Import validation still runs locally. Only an item stored with the accepted
    code is eligible for the practice queue; rejected and flagged items remain
    in the database for traceability.
    """

    ACCEPTED = 1
    REJECTED = 2
    FLAGGED = 3


RESPONSE_TYPE_CHOICES = [
    (item.value, item.name.replace('_', ' ').capitalize()) for item in ResponseType
]
VALIDATION_STATUS_CHOICES = [
    (item.value, item.name.capitalize()) for item in ValidationStatus
]


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
    response_type = models.IntegerField(choices=RESPONSE_TYPE_CHOICES)
    requested_difficulty = models.IntegerField()
    assessed_difficulty = models.IntegerField(null=True, blank=True)
    source_question_ids = models.JSONField()
    generation_config = models.JSONField()
    validation_status = models.IntegerField(choices=VALIDATION_STATUS_CHOICES)
    validation_reasons = models.JSONField()

    class Meta:
        """Define the index used when selecting practice questions.

        The composite index follows the skill, grade, and validation-status
        filters applied before choosing an eligible item.
        """

        indexes = [
            models.Index(
                fields=['skill', 'grade', 'validation_status'],
                name='question_selection_idx',
            ),
        ]

    def __str__(self):
        """Return the question's upstream identifier as its display value.

        The primary key is preserved during import and is also the ID exposed
        by question and attempt responses.
        """

        return self.pk
