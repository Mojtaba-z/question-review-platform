"""Create repeatable sample users, skills, questions, and attempts."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.constants import STUDENT_GROUP, TEACHER_GROUP
from accounts.models import Student
from accounts.services.roles import RoleService
from practice.models import Attempt
from question_bank.models import QuestionItem, Skill, ValidationStatus
from question_bank.services.import_questions import QuestionImportService


class Command(BaseCommand):
    """Populate a demonstration database after migrations exist.

    Creates two grade-three skills, fifteen imported questions with mixed
    statuses, one teacher, three students, and pending/correct/incorrect
    attempts. Re-running the command reuses existing records and preserves
    passwords for existing accounts.
    """

    help = 'Create two skills, fifteen questions, sample users, and sample attempts.'

    def add_arguments(self, parser):
        """Add the password option used only for newly created demo users.

        Args:
            parser: Django's command-line argument parser.

        Returns:
            None; ``--password`` becomes a required command option.
        """

        parser.add_argument('--password', required=True)

    def handle(self, *args, **options):
        """Create or reuse sample records and print the question count.

        Args:
            *args: Positional command arguments; this command uses none.
            **options: Parsed options including the required ``password``.

        Returns:
            None. A success message is written to stdout, and skipped
            question details are written to stderr if an import fails.
        """

        password = options['password']
        user_model = get_user_model()
        RoleService.ensure_groups()

        users = {}
        for username, role in (
            ('teacher1', TEACHER_GROUP),
            ('student1', STUDENT_GROUP),
            ('student2', STUDENT_GROUP),
            ('student3', STUDENT_GROUP),
        ):
            user, created = user_model.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.save(update_fields=['password'])
            RoleService.assign_role(user, role)
            if role == STUDENT_GROUP:
                Student.objects.get_or_create(user=user, defaults={'grade': 3})
            users[username] = user

        for slug, name, objective in (
            ('two_digit_addition', 'Two-Digit Addition', 'Add two-digit numbers.'),
            ('simple_fractions', 'Simple Fractions', 'Identify simple fractions.'),
        ):
            Skill.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'grade': 3, 'learning_objective': objective},
            )

        items = []
        for number in range(1, 16):
            item_id = f'qgen_{number:03d}'
            if QuestionItem.objects.filter(pk=item_id).exists():
                continue
            skill = 'two_digit_addition' if number <= 8 else 'simple_fractions'
            prompt = (
                f'What is {number + 20} + {number + 10}?'
                if number <= 8
                else f'What fraction is {number - 8} out of 10?'
            )
            status = (
                ValidationStatus.ACCEPTED if number <= 10
                else ValidationStatus.REJECTED if number <= 13
                else ValidationStatus.FLAGGED
            )
            items.append({
                'id': item_id,
                'skill': skill,
                'grade': 3,
                'prompt_en': prompt,
                'response_type': 'short_text',
                'requested_difficulty': 2,
                'assessed_difficulty': 2,
                'source_question_ids': [f'wk_{number:03d}'],
                'generation_config': {'prompt_version': 'demo'},
                'validation_status': status,
                'validation_reasons': ['demo_seed'],
            })

        result = QuestionImportService.import_batch(items)
        if result['errors']:
            self.stderr.write(f'Some sample questions were skipped: {result["errors"]}')

        sample_attempts = (
            ('student1', 'qgen_001', '32', None),
            ('student2', 'qgen_002', '34', True),
            ('student3', 'qgen_003', '44', False),
        )
        for username, question_id, answer, correct in sample_attempts:
            Attempt.objects.get_or_create(
                student=Student.objects.get(user=users[username]),
                question_item=QuestionItem.objects.get(pk=question_id),
                defaults={
                    'submitted_answer': answer,
                    'reviewed_correct': correct,
                    'reviewed_by': users['teacher1'] if correct is not None else None,
                },
            )

        self.stdout.write(self.style.SUCCESS(f'Created {len(result["created"])} questions.'))
