"""Serializers for the upstream contract and learner-facing questions."""

from rest_framework import serializers

from question_bank.models import QuestionItem, ResponseType, ValidationStatus


class QuestionImportSerializer(serializers.Serializer):
    """Check one item against the generator's required JSON structure.

    Input is a question object with its ID, skill slug, grade, prompt, response
    type, difficulties, source IDs, generation metadata, and upstream validation
    fields. Output is ``validated_data`` with those primitive values. This class
    checks field presence and types; the import service checks that the skill
    exists, grades match, and the ID and prompt are new.
    """

    id = serializers.CharField(max_length=255)
    skill = serializers.SlugField()
    grade = serializers.IntegerField(min_value=1, max_value=12)
    prompt_en = serializers.CharField(allow_blank=False)
    response_type = serializers.ChoiceField(choices=ResponseType.choices)
    requested_difficulty = serializers.IntegerField()
    assessed_difficulty = serializers.IntegerField(allow_null=True)
    source_question_ids = serializers.ListField(child=serializers.CharField())
    generation_config = serializers.DictField()
    validation_status = serializers.ChoiceField(choices=ValidationStatus.choices)
    validation_reasons = serializers.ListField(child=serializers.CharField())


class PracticeQuestionSerializer(serializers.ModelSerializer):
    """Turn a stored question into the learner-facing response.

    Input is a ``QuestionItem`` selected by the practice service. Output
    contains its ID, skill slug, grade, prompt, and response type. Generation
    metadata, validation notes, and internal duplicate hash are omitted.
    """

    skill = serializers.CharField(source='skill_id')

    class Meta:
        """Declare the five question fields students may receive."""

        model = QuestionItem
        fields = ('id', 'skill', 'grade', 'prompt_en', 'response_type')
