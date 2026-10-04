"""Question bank URLs."""

from django.urls import path

from question_bank.views import QuestionImportView

urlpatterns = [
    path('import/', QuestionImportView.as_view(), name='question-import'),
]
