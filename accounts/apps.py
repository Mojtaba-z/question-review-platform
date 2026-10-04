from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Identify the accounts app and its default primary-key type.

    Django uses this configuration when loading student profiles, account
    endpoints, and the app's management and test modules.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
