"""Role names and the Django permissions granted to each role."""

STUDENT_GROUP = 'student'
TEACHER_GROUP = 'teacher'

ROLE_PERMISSIONS = {
    STUDENT_GROUP: (
        'question_bank.view_questionitem',
        'practice.add_attempt',
    ),
    TEACHER_GROUP: (
        'question_bank.add_questionitem',
        'practice.view_attempt',
        'practice.change_attempt',
    ),
}
