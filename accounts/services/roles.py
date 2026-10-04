"""Keep Django groups and their model permissions ready for use."""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from accounts.constants import ROLE_PERMISSIONS, STUDENT_GROUP, TEACHER_GROUP
from accounts.exception import AccountInputError


class RoleService:
    """Manage student and teacher roles with Django's built-in Group model.

    The service makes the two groups and their endpoint permissions available
    without a data migration. It changes only these role groups when assigning
    a user, leaving any unrelated Django groups intact.
    """

    @staticmethod
    def ensure_groups():
        """Create missing role groups and attach their model permissions.

        The operation is repeatable: existing groups and permissions are reused
        and permissions are added without removing administrator-added ones.

        Returns:
            A dictionary keyed by the student and teacher role names, with
            their ``Group`` instances as values.
        """

        groups = {}
        for role, permission_codes in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=role)
            for code in permission_codes:
                app_label, codename = code.split('.')
                action, model_name = codename.split('_', 1)
                content_type, _ = ContentType.objects.get_or_create(
                    app_label=app_label, model=model_name
                )
                permission, _ = Permission.objects.get_or_create(
                    content_type=content_type,
                    codename=codename,
                    defaults={'name': f'Can {action} {model_name}'},
                )
                group.permissions.add(permission)
            groups[role] = group
        return groups

    @staticmethod
    def assign_role(user, role):
        """Give a user exactly one of the two platform roles.

        Existing student and teacher memberships are removed first. Membership
        in groups unrelated to these roles is preserved. Missing groups and
        permissions are created through ``ensure_groups``.

        Args:
            user: Saved Django user whose groups will change.
            role: Either the student or teacher group name.

        Returns:
            The assigned ``Group`` instance.

        Raises:
            AccountInputError: If ``role`` is not a supported role name.
        """

        if role not in ROLE_PERMISSIONS:
            raise AccountInputError(f'Unknown role: {role}')
        group = RoleService.ensure_groups()[role]
        user.groups.remove(*user.groups.filter(name__in=[STUDENT_GROUP, TEACHER_GROUP]))
        user.groups.add(group)
        return group
