from django.apps import AppConfig


class QuestionBankConfig(AppConfig):
    """Identify the question bank app and its default primary-key type.

    Django uses this configuration to load skills, imported questions, the
    seed command, and the app's URL and service modules.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'question_bank'
