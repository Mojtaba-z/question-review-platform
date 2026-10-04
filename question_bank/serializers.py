"""Serializers for the upstream contract and learner-facing questions."""

from rest_framework import serializers

from question_bank.models import (
    QuestionItem, RESPONSE_TYPE_CHOICES, VALIDATION_STATUS_CHOICES,
)


class QuestionImportSerializer(serializers.Serializer):
    """Check one item against the generator's required JSON structure.

    Input is a question object with its ID, skill slug, grade, prompt, response
    type code, difficulties, source IDs, generation metadata, and numeric
    validation status. Output is ``validated_data`` with those primitive
    values. This class checks field presence and types; the import service
    checks that the skill exists, grades match, and the ID and prompt are new.
    """

    id = serializers.CharField(max_length=255)
    skill = serializers.SlugField()
    grade = serializers.IntegerField(min_value=1, max_value=12)
    prompt_en = serializers.CharField(allow_blank=False)
    response_type = serializers.ChoiceField(choices=RESPONSE_TYPE_CHOICES)
    requested_difficulty = serializers.IntegerField()
    assessed_difficulty = serializers.IntegerField(allow_null=True)
    source_question_ids = serializers.ListField(child=serializers.CharField())
    generation_config = serializers.DictField()
    validation_status = serializers.ChoiceField(choices=VALIDATION_STATUS_CHOICES)
    validation_reasons = serializers.ListField(child=serializers.CharField())


class PracticeQuestionSerializer(serializers.ModelSerializer):
    """Turn a stored question into the learner-facing response.

    Input is a ``QuestionItem`` selected by the practice service. Output
    contains its ID, skill slug, grade, prompt, and numeric response type. Generation
    metadata, validation notes, and internal duplicate hash are omitted.
    """

    skill = serializers.CharField(source='skill_id')

    class Meta:
        """Select the model and fields for learner-facing output.

        Only the question ID, skill slug, grade, prompt, and response type
        appear in the serialized practice question.
        """

        model = QuestionItem
        fields = ('id', 'skill', 'grade', 'prompt_en', 'response_type')
