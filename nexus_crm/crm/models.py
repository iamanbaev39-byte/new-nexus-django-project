from django.db import models
from django.utils import timezone


class Course(models.Model):
    name = models.CharField(max_length=120, unique=True)
    monthly_fee = models.FloatField(default=0)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "courses"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Teacher(models.Model):
    SALARY_TYPES = [("fixed", "Fiks"), ("per_lesson", "Darsbay")]
    STATUSES = [("active", "Faol"), ("inactive", "Nofaol")]

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40)
    email = models.CharField(max_length=120, blank=True, null=True)
    subject = models.CharField(max_length=120)
    salary_type = models.CharField(max_length=30, choices=SALARY_TYPES, default="fixed")
    salary_amount = models.FloatField(default=0)
    employment_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=STATUSES, default="active")

    class Meta:
        db_table = "teachers"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class StudyGroup(models.Model):
    name = models.CharField(max_length=120)
    schedule_info = models.CharField(max_length=120, blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="groups")
    teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, related_name="groups", blank=True, null=True
    )

    class Meta:
        db_table = "study_groups"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Student(models.Model):
    PAYMENT_STATUSES = [("paid", "To‘langan"), ("unpaid", "To‘lanmagan")]

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40)
    parent_phone = models.CharField(max_length=40, blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="students")
    group = models.ForeignKey(
        StudyGroup, on_delete=models.SET_NULL, related_name="students", blank=True, null=True
    )
    registration_date = models.DateField(default=timezone.localdate)
    monthly_fee = models.FloatField(default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUSES, default="unpaid")

    class Meta:
        db_table = "students"
        ordering = ["-id"]

    def __str__(self):
        return self.full_name


class Lesson(models.Model):
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="lessons")
    teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, blank=True, null=True, related_name="lessons"
    )
    lesson_date = models.DateField(default=timezone.localdate)
    topic = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = "lessons"
        ordering = ["-lesson_date", "-id"]

    def __str__(self):
        return f"{self.group} - {self.lesson_date}"


class AttendanceRecord(models.Model):
    STATUSES = [("present", "Keldi"), ("late", "Kechikdi"), ("absent", "Kelmadi")]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendances")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="attendances")
    status = models.CharField(max_length=20, choices=STATUSES, default="present")
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "attendance_records"
        constraints = [
            models.UniqueConstraint(fields=["student", "lesson"], name="uq_student_lesson_attendance")
        ]


class SalaryRecord(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="payrolls")
    month_key = models.CharField(max_length=7)
    base_salary = models.FloatField(default=0)
    bonus = models.FloatField(default=0)
    deductions = models.FloatField(default=0)
    total_payable = models.FloatField(default=0)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "salary_records"
        constraints = [
            models.UniqueConstraint(fields=["teacher", "month_key"], name="uq_teacher_month_salary")
        ]


class Expense(models.Model):
    title = models.CharField(max_length=160)
    category = models.CharField(max_length=80, default="General")
    amount = models.FloatField(default=0)
    expense_date = models.DateField(default=timezone.localdate)

    class Meta:
        db_table = "expenses"


class Notification(models.Model):
    title = models.CharField(max_length=160)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]


class ActivityLog(models.Model):
    user = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_activity_logs"
    )
    action = models.CharField(max_length=240)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "activity_logs"
        ordering = ["-created_at"]


class OrganizationSettings(models.Model):
    name = models.CharField(max_length=160, default="NEXUS")
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=240, blank=True)

    class Meta:
        db_table = "organization_settings"
