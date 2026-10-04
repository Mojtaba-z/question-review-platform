"""Practice, attempt, report, and health URLs."""

from django.urls import path

from practice.views import (
    ActivityReportView, AttemptSubmitView, HealthView, NextQuestionView,
    PendingAttemptsView, ReviewAttemptView,
)

urlpatterns = [
    path('practice/next/', NextQuestionView.as_view(), name='practice-next'),
    path('attempts/', AttemptSubmitView.as_view(), name='attempt-submit'),
    path('attempts/pending/', PendingAttemptsView.as_view(), name='attempts-pending'),
    path('attempts/<int:attempt_id>/review/', ReviewAttemptView.as_view(), name='attempt-review'),
    path('reports/activity/', ActivityReportView.as_view(), name='activity-report'),
    path('health/', HealthView.as_view(), name='health'),
]
