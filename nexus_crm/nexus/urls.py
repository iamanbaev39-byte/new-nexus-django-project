from django.urls import path

from crm import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("account", views.account_settings, name="account_settings"),
    path("users", views.users_view, name="users_view"),
    path("reports", views.reports_view, name="reports"),
    path("notifications", views.notifications_view, name="notifications"),
    path("settings", views.settings_view, name="settings"),
    path("activity", views.activity_view, name="activity"),
    path("teachers", views.teachers_list, name="teachers_list"),
    path("teachers/new", views.teacher_create, name="teacher_create"),
    path("teachers/<int:teacher_id>/edit", views.teacher_edit, name="teacher_edit"),
    path("teachers/<int:teacher_id>/delete", views.teacher_delete, name="teacher_delete"),
    path("students", views.students_list, name="students_list"),
    path("students/new", views.student_create, name="student_create"),
    path("students/<int:student_id>/edit", views.student_edit, name="student_edit"),
    path("students/<int:student_id>/delete", views.student_delete, name="student_delete"),
    path("courses", views.courses_view, name="courses_view"),
    path("courses/<int:course_id>/delete", views.course_delete, name="course_delete"),
    path("groups/<int:group_id>/delete", views.group_delete, name="group_delete"),
    path("attendance", views.attendance_view, name="attendance_view"),
    path("attendance/lesson/<int:lesson_id>", views.mark_attendance, name="mark_attendance"),
    path("attendance/lesson/<int:lesson_id>/delete", views.lesson_delete, name="lesson_delete"),
    path("payroll", views.payroll_view, name="payroll_view"),
]

handler403 = "crm.views.permission_denied"
handler404 = "crm.views.page_not_found"
handler500 = "crm.views.server_error"
