"""Database connectivity check used by the health endpoint."""

from django.db import DatabaseError, connection


class HealthService:
    """Provide the database portion of the public application health check.

    The view calls this service rather than embedding a SQL query in HTTP code.
    A failed database connection becomes a False result for an HTTP 503.
    """

    @staticmethod
    def database_is_ready():
        """Run a lightweight query against the configured database.

        Returns:
            True when ``SELECT 1`` returns 1; False if a Django database error
            prevents a successful query. No application records are modified.
        """

        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                return cursor.fetchone()[0] == 1
        except DatabaseError:
            return False
