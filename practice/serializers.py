"""Serializers for attempts, reviews, and activity reports."""

from rest_framework import serializers

from practice.models import Attempt


class AttemptSubmitSerializer(serializers.Serializer):
    """Check the shape of a student answer submission.

    Input is JSON with a ``question_item`` ID, nonblank ``submitted_answer``,
    and optional nonnegative ``time_spent_seconds``. Output is those primitive
    values in ``validated_data`` for ``AttemptService.submit``. The client
    cannot submit review state or reviewer identity.
    """

    question_item = serializers.CharField(max_length=255)
    submitted_answer = serializers.CharField(allow_blank=False)
    time_spent_seconds = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class ReviewSerializer(serializers.Serializer):
    """Check the decision supplied for a pending attempt.

    Input is JSON with required ``correct``. Output is the validated boolean
    in ``validated_data`` for ``AttemptService.review``. The reviewer identity
    is taken from the authenticated request, never from this payload.
    """

    correct = serializers.BooleanField()


class ActivityQuerySerializer(serializers.Serializer):
    """Check filters for a teacher's activity report request.

    Input is a positive ``student`` profile ID and a ``skill`` slug from query
    parameters. Output is those validated values for the report service. It
    does not check existence; the service does that against the database.
    """

    student = serializers.IntegerField(min_value=1)
    skill = serializers.SlugField()


class AttemptSerializer(serializers.ModelSerializer):
    """Expose a stored attempt and its manual-review state.

    Input is an ``Attempt`` instance or queryset. Output contains its student
    and question IDs, submitted text, optional time spent, creation time,
    nullable correctness, and reviewer ID. No answer key exists to expose.
    """

    class Meta:
        """Select the model and fields for attempt responses.

        The response includes submission details and nullable review fields,
        allowing callers to distinguish pending from reviewed attempts.
        """

        model = Attempt
        fields = (
            'id', 'student', 'question_item', 'submitted_answer',
            'reviewed_correct', 'reviewed_by', 'time_spent_seconds', 'created_at',
        )
