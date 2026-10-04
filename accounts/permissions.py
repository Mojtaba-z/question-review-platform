"""Permissions backed by Django's student and teacher groups."""

from rest_framework.permissions import BasePermission

from .constants import STUDENT_GROUP, TEACHER_GROUP


class IsStudent(BasePermission):
    """Protect a student endpoint with Django group and model permissions.

    The view must declare ``required_permission``. Membership in the student
    group alone is insufficient; the user must also hold that permission.
    """

    def has_permission(self, request, view):
        """Check the request user against the view's student permission.

        Args:
            request: DRF request containing the authenticated user.
            view: APIView declaring ``required_permission``.

        Returns:
            True only for authenticated student-group users with the named
            Django permission; otherwise False.
        """

        user = request.user
        return bool(
            user.is_authenticated
            and user.groups.filter(name=STUDENT_GROUP).exists()
            and user.has_perm(view.required_permission)
        )


class IsTeacher(BasePermission):
    """Protect a teacher endpoint with Django group and model permissions.

    The view must declare ``required_permission``. The group check prevents a
    user with a direct permission but no teacher role from using the endpoint.
    """

    def has_permission(self, request, view):
        """Check the request user against the view's teacher permission.

        Args:
            request: DRF request containing the authenticated user.
            view: APIView declaring ``required_permission``.

        Returns:
            True only for authenticated teacher-group users with the named
            Django permission; otherwise False.
        """

        user = request.user
        return bool(
            user.is_authenticated
            and user.groups.filter(name=TEACHER_GROUP).exists()
            and user.has_perm(view.required_permission)
        )
