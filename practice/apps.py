from django.apps import AppConfig


class PracticeConfig(AppConfig):
    """Identify the practice app and its default primary-key type.

    Django uses this configuration to load attempts, review/report endpoints,
    and the associated services and tests.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'practice'
