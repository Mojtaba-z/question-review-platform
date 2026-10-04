"""Question import API endpoint."""

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsTeacher
from question_bank.services.import_questions import QuestionImportService


class QuestionImportView(APIView):
    """Teacher-only endpoint for importing the upstream question contract.

    POST ``/api/questions/import/`` requires the teacher group and Django's
    ``add_questionitem`` permission. The request body is an array; response
    details distinguish created items from per-item validation failures.
    """

    permission_classes = [IsTeacher]
    required_permission = 'question_bank.add_questionitem'

    def post(self, request):
        """Pass the batch to the import service and return partial results.

        Args:
            request: Authenticated DRF request with an upstream JSON array.

        Returns:
            HTTP 200 with ``created`` IDs and ``errors`` per invalid item.

        Raises:
            QuestionInputError: If the body is not an array.
        """

        result = QuestionImportService.import_batch(request.data)
        return Response(result)
