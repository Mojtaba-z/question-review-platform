"""Import upstream questions with per-item validation results."""

from hashlib import sha256

from django.db import IntegrityError, transaction

from question_bank.exception import QuestionInputError
from question_bank.models import QuestionItem, Skill
from question_bank.serializers import QuestionImportSerializer


class QuestionImportService:
    """Apply local import rules to an upstream batch, item by item.

    Structural checks come from ``QuestionImportSerializer``. This service
    resolves skills, requires the question grade to match the skill grade,
    detects repeated IDs/prompts, and stores valid items with their upstream
    accepted, rejected, or flagged status unchanged. Each item has its own
    result so one invalid item does not fail the whole batch.
    """

    @staticmethod
    def normalize_prompt(prompt):
        """Prepare question text for exact normalized duplicate detection.

        Args:
            prompt: Question text from a serializer-validated item.

        Returns:
            The lowercase text with leading/trailing whitespace removed and
            each run of whitespace replaced by one space. Distinct wording is
            not treated as a duplicate.
        """

        return ' '.join(prompt.lower().split())

    @staticmethod
    def import_batch(items):
        """Validate and persist every item that passes local checks.

        For each item, validate fields, resolve the existing skill, compare its
        grade, and reject a repeated upstream ID or normalized prompt. A
        database uniqueness error is reported for that item, including a
        concurrent import race, while other items continue.

        Args:
            items: Top-level JSON array of upstream question objects.

        Returns:
            A mapping with ``created`` (stored IDs in input order) and
            ``errors`` (ID and field-error mapping for each rejected item).

        Raises:
            QuestionInputError: If the top-level value is not a JSON array.
        """

        if not isinstance(items, list):
            raise QuestionInputError('Expected a JSON array of question items.')

        created = []
        errors = []
        seen_hashes = set()

        for item in items:
            item_id = item.get('id') if isinstance(item, dict) else None
            serializer = QuestionImportSerializer(data=item)
            if not serializer.is_valid():
                errors.append({'id': item_id, 'errors': serializer.errors})
                continue

            data = serializer.validated_data
            skill = Skill.objects.filter(pk=data['skill']).first()
            if skill is None:
                errors.append({'id': item_id, 'errors': {'skill': ['Unknown skill.']}})
                continue
            if skill.grade != data['grade']:
                errors.append({'id': item_id, 'errors': {'grade': ['Grade must match the skill.']}})
                continue

            normalized = QuestionImportService.normalize_prompt(data['prompt_en'])
            prompt_hash = sha256(normalized.encode('utf-8')).hexdigest()
            if (
                prompt_hash in seen_hashes
                or QuestionItem.objects.filter(prompt_hash=prompt_hash).exists()
                or QuestionItem.objects.filter(pk=data['id']).exists()
            ):
                errors.append({'id': item_id, 'errors': {'id': ['Duplicate ID or prompt.']}})
                continue

            try:
                with transaction.atomic():
                    QuestionItem.objects.create(
                        id=data['id'],
                        skill=skill,
                        grade=data['grade'],
                        prompt_en=data['prompt_en'],
                        prompt_hash=prompt_hash,
                        response_type=data['response_type'],
                        requested_difficulty=data['requested_difficulty'],
                        assessed_difficulty=data['assessed_difficulty'],
                        source_question_ids=data['source_question_ids'],
                        generation_config=data['generation_config'],
                        validation_status=data['validation_status'],
                        validation_reasons=data['validation_reasons'],
                    )
            except IntegrityError:
                errors.append({'id': item_id, 'errors': {'id': ['Duplicate ID or prompt.']}})
                continue

            seen_hashes.add(prompt_hash)
            created.append(data['id'])

        return {'created': created, 'errors': errors}
