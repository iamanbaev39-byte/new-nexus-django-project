import calendar
from datetime import datetime, timedelta
from functools import wraps
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    AttendanceRecord,
    Course,
    Expense,
    Lesson,
    SalaryRecord,
    Student,
    StudyGroup,
    Teacher,
    Notification,
    ActivityLog,
    OrganizationSettings,
)


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return render(request, "errors/403.html", status=403)
        return view_func(request, *args, **kwargs)

    return wrapped


def parse_nonnegative_float(value, field_name="Qiymat"):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} raqam boâ€˜lishi kerak.")
    if number < 0:
        raise ValueError(f"{field_name} manfiy boâ€˜lmasligi kerak.")
    return round(number, 2)


def calculate_teacher_month_salary(teacher, month_key, bonus=0.0, deductions=0.0):
    try:
        start = datetime.strptime(month_key, "%Y-%m").date().replace(day=1)
    except ValueError:
        raise ValueError("Oy formati notoâ€˜gâ€˜ri.")
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    lessons_count = Lesson.objects.filter(
        teacher_id=teacher.id, lesson_date__range=(start, end)
    ).count()
    base_salary = (
        float(teacher.salary_amount) * lessons_count
        if teacher.salary_type == "per_lesson"
        else float(teacher.salary_amount)
    )
    total = max(0.0, base_salary + float(bonus) - float(deductions))
    return round(base_salary, 2), round(total, 2), lessons_count


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        user = authenticate(request, username=username, password=request.POST.get("password", ""))
        if user is not None:
            login(request, user)
            messages.success(request, f"Xush kelibsiz, {user.get_full_name() or user.get_username()}!")
            return redirect("dashboard")
        messages.error(request, "Login yoki parol notoâ€˜gâ€˜ri.")
    return render(request, "login.html")


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Tizimdan chiqdingiz.")
    return redirect("login")


@login_required
def account_settings(request):
    user = request.user

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        current_password = request.POST.get("current_password", "")
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not username:
            messages.error(request, "Login bo‘sh bo‘lmasligi kerak.")
        elif not current_password:
            messages.error(request, "O‘zgarishlar uchun joriy parolni kiriting.")
        elif not user.check_password(current_password):
            messages.error(request, "Joriy parol noto‘g‘ri.")
        else:
            try:
                if username != user.username:
                    existing_user = get_user_model().objects.filter(username__iexact=username).exclude(pk=user.pk)
                    if existing_user.exists():
                        raise ValueError("Bu login band.")
                    user.username = username

                if new_password or confirm_password:
                    if new_password != confirm_password:
                        raise ValueError("Yangi parol va tasdiqlash paroli bir xil emas.")
                    validate_password(new_password, user)
                    user.set_password(new_password)

                user.save()
                if new_password:
                    update_session_auth_hash(request, user)
                messages.success(request, "Hisob ma’lumotlari yangilandi.")
                return redirect("account_settings")
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
            except (ValueError, IntegrityError) as exc:
                messages.error(request, str(exc) or "Hisob ma’lumotlarini saqlashda xatolik.")

    return render(request, "account_settings.html", {"account_user": user})


@admin_required
def users_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            username = request.POST.get("username", "").strip()
            password = request.POST.get("password", "")
            role = request.POST.get("role", "staff")
            if not username or not password:
                messages.error(request, "Login va parol majburiy.")
            elif get_user_model().objects.filter(username__iexact=username).exists():
                messages.error(request, "Bu login band.")
            else:
                user_model = get_user_model()
                if role == "admin":
                    user = user_model.objects.create_superuser(username=username, email="", password=password)
                else:
                    user = user_model.objects.create_user(username=username, email="", password=password)
                    user.is_staff = False
                    user.save(update_fields=["is_staff"])
                ActivityLog.objects.create(user=request.user, action=f"{username} foydalanuvchi qo‘shildi")
                messages.success(request, "Foydalanuvchi qo‘shildi.")
        elif action == "toggle":
            user = get_object_or_404(get_user_model(), pk=int(request.POST["user_id"]))
            if user == request.user:
                messages.error(request, "O‘z hisobingizni o‘chira olmaysiz.")
            else:
                user.is_active = not user.is_active
                user.save(update_fields=["is_active"])
                ActivityLog.objects.create(
                    user=request.user,
                    action=f"{user.username} hisobining holati o‘zgartirildi",
                )
                messages.success(request, "Foydalanuvchi holati o‘zgartirildi.")
        return redirect("users_view")
    return render(request, "users.html", {"users": get_user_model().objects.all().order_by("username")})


@admin_required
def reports_view(request):
    month_key = request.GET.get("month") or timezone.localdate().strftime("%Y-%m")
    try:
        month_start = datetime.strptime(month_key, "%Y-%m").date().replace(day=1)
    except ValueError:
        month_key = timezone.localdate().strftime("%Y-%m")
        month_start = timezone.localdate().replace(day=1)
    month_end = month_start.replace(
        day=calendar.monthrange(month_start.year, month_start.month)[1]
    )
    return render(
        request,
        "reports.html",
        {
            "month_key": month_key,
            "students": Student.objects.count(),
            "paid_students": Student.objects.filter(payment_status="paid").count(),
            "unpaid_students": Student.objects.filter(payment_status="unpaid").count(),
            "monthly_income": Student.objects.filter(payment_status="paid").aggregate(total=Sum("monthly_fee"))["total"] or 0,
            "salary_expenses": SalaryRecord.objects.filter(month_key=month_key).aggregate(total=Sum("total_payable"))["total"] or 0,
            "other_expenses": Expense.objects.filter(
                expense_date__range=(month_start, month_end)
            ).aggregate(total=Sum("amount"))["total"] or 0,
            "attendance_records": AttendanceRecord.objects.filter(
                lesson__lesson_date__range=(month_start, month_end)
            ).count(),
        },
    )


@login_required
def notifications_view(request):
    unpaid_count = Student.objects.filter(payment_status="unpaid").count()
    notifications = list(Notification.objects.all())
    if unpaid_count:
        notifications.insert(
            0,
            SimpleNamespace(
                title="To‘lov eslatmasi",
                message=f"{unpaid_count} o‘quvchining oylik to‘lovi hali amalga oshirilmagan.",
                is_read=False,
                created_at=timezone.now(),
            ),
        )
    if request.method == "POST":
        Notification.objects.update(is_read=True)
        messages.success(request, "Barcha bildirishnomalar o‘qildi.")
        return redirect("notifications")
    return render(request, "notifications.html", {"notifications": notifications})


@admin_required
def settings_view(request):
    settings_obj, _ = OrganizationSettings.objects.get_or_create(pk=1)
    if request.method == "POST":
        settings_obj.name = request.POST.get("name", "").strip() or "NEXUS"
        settings_obj.phone = request.POST.get("phone", "").strip()
        settings_obj.address = request.POST.get("address", "").strip()
        settings_obj.save()
        ActivityLog.objects.create(user=request.user, action="Tashkilot sozlamalari yangilandi")
        messages.success(request, "Sozlamalar saqlandi.")
        return redirect("settings")
    return render(request, "settings.html", {"settings_obj": settings_obj})


@admin_required
def activity_view(request):
    return render(request, "activity.html", {"logs": ActivityLog.objects.select_related("user").all()[:200]})


@login_required
def dashboard(request):
    today = timezone.localdate()
    month_key = today.strftime("%Y-%m")
    today_records = list(
        AttendanceRecord.objects.filter(lesson__lesson_date=today).values_list("status", flat=True)
    )
    attendance_pct = (
        round(sum(status in ("present", "late") for status in today_records) * 100 / len(today_records), 1)
        if today_records
        else 0.0
    )
    monthly_income = (
        Student.objects.filter(payment_status="paid").aggregate(total=Sum("monthly_fee"))["total"] or 0
    )
    total_salary_expenses = (
        SalaryRecord.objects.filter(month_key=month_key).aggregate(total=Sum("total_payable"))["total"]
        or 0
    )
    other_expenses = (
        Expense.objects.filter(expense_date__year=today.year, expense_date__month=today.month)
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )
    course_rows = Course.objects.annotate(student_count=Count("students")).order_by(
        "-student_count", "name"
    )
    attendance_labels = []
    attendance_values = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        statuses = list(
            AttendanceRecord.objects.filter(lesson__lesson_date=day).values_list("status", flat=True)
        )
        attendance_labels.append(day.strftime("%d.%m"))
        attendance_values.append(
            round(sum(status in ("present", "late") for status in statuses) * 100 / len(statuses), 1)
            if statuses
            else 0.0
        )
    context = {
        "total_students": Student.objects.count(),
        "total_teachers": Teacher.objects.filter(status="active").count(),
        "active_courses": Course.objects.filter(is_active=True).count(),
        "new_registrations": Student.objects.filter(
            registration_date__year=today.year, registration_date__month=today.month
        ).count(),
        "attendance_pct": attendance_pct,
        "monthly_income": round(float(monthly_income), 2),
        "total_salary_expenses": round(float(total_salary_expenses), 2),
        "monthly_expenses": round(float(total_salary_expenses) + float(other_expenses), 2),
        "total_groups": StudyGroup.objects.count(),
        "paid_students": Student.objects.filter(payment_status="paid").count(),
        "unpaid_students": Student.objects.filter(payment_status="unpaid").count(),
        "inactive_teachers": Teacher.objects.filter(status="inactive").count(),
        "net_profit": round(float(monthly_income) - float(total_salary_expenses) - float(other_expenses), 2),
        "course_labels": [course.name for course in course_rows],
        "course_values": [course.student_count for course in course_rows],
        "attendance_labels": attendance_labels,
        "attendance_values": attendance_values,
    }
    return render(request, "dashboard.html", context)


@login_required
def teachers_list(request):
    query = request.GET.get("q", "").strip()
    teachers = Teacher.objects.all()
    if query:
        teachers = teachers.filter(
            Q(full_name__icontains=query) | Q(subject__icontains=query) | Q(phone__icontains=query)
        )
    return render(request, "teachers.html", {"teachers": teachers, "q": query})


def teacher_form(request, teacher=None):
    if request.method == "POST":
        try:
            is_new = teacher.pk is None
            full_name = request.POST.get("full_name", "").strip()
            phone = request.POST.get("phone", "").strip()
            subject = request.POST.get("subject", "").strip()
            if not full_name or not phone or not subject:
                raise ValueError("Ism, telefon va fan maydonlari majburiy.")
            employment_date = request.POST.get("employment_date", "")
            teacher.full_name = full_name
            teacher.phone = phone
            teacher.email = request.POST.get("email", "").strip()
            teacher.subject = subject
            teacher.salary_type = request.POST.get("salary_type", "fixed")
            if teacher.salary_type not in ("fixed", "per_lesson"):
                raise ValueError("Ish haqi turi notoâ€˜gâ€˜ri.")
            teacher.salary_amount = parse_nonnegative_float(request.POST.get("salary_amount"), "Ish haqi")
            if employment_date:
                teacher.employment_date = datetime.strptime(employment_date, "%Y-%m-%d").date()
            teacher.status = request.POST.get("status", "active")
            if teacher.status not in ("active", "inactive"):
                raise ValueError("Holat notoâ€˜gâ€˜ri.")
            teacher.save()
            messages.success(
                request,
                "Oâ€˜qituvchi maâ€™lumotlari yangilandi."
                if not is_new
                else "Oâ€˜qituvchi muvaffaqiyatli qoâ€˜shildi.",
            )
            return redirect("teachers_list")
        except (ValueError, IntegrityError) as exc:
            messages.error(request, str(exc) or "Maâ€™lumotlarni saqlashda xatolik yuz berdi.")
    return render(request, "teacher_form.html", {"teacher": teacher})


@admin_required
def teacher_create(request):
    teacher = Teacher()
    return teacher_form(request, teacher)


@admin_required
def teacher_edit(request, teacher_id):
    return teacher_form(request, get_object_or_404(Teacher, pk=teacher_id))


@require_POST
@admin_required
def teacher_delete(request, teacher_id):
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    if teacher.groups.exists() or teacher.payrolls.exists():
        messages.error(request, "Bu oâ€˜qituvchiga guruh yoki ish haqi yozuvi biriktirilgan.")
    else:
        teacher.delete()
        messages.info(request, "Oâ€˜qituvchi oâ€˜chirildi.")
    return redirect("teachers_list")


@login_required
def students_list(request):
    query = request.GET.get("q", "").strip()
    students = Student.objects.select_related("course", "group")
    if query:
        students = students.filter(
            Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(parent_phone__icontains=query)
        )
    return render(request, "students.html", {"students": students, "q": query})


def student_form(request, student=None):
    courses = Course.objects.filter(is_active=True)
    groups = StudyGroup.objects.select_related("course")
    if request.method == "POST":
        try:
            is_new = student.pk is None
            full_name = request.POST.get("full_name", "").strip()
            phone = request.POST.get("phone", "").strip()
            if not full_name or not phone:
                raise ValueError("Ism va telefon maydonlari majburiy.")
            course = get_object_or_404(Course, pk=int(request.POST["course_id"]))
            group_value = request.POST.get("group_id")
            group = get_object_or_404(StudyGroup, pk=int(group_value)) if group_value else None
            if group and group.course_id != course.id:
                raise ValueError("Guruh tanlangan kursga tegishli emas.")
            status = request.POST.get("payment_status", "unpaid")
            if status not in ("paid", "unpaid"):
                raise ValueError("Toâ€˜lov holati notoâ€˜gâ€˜ri.")
            fee_value = request.POST.get("monthly_fee")
            monthly_fee = parse_nonnegative_float(
                fee_value if fee_value not in (None, "") else course.monthly_fee, "Toâ€˜lov"
            )
            student.full_name = full_name
            student.phone = phone
            student.parent_phone = request.POST.get("parent_phone", "").strip()
            student.course = course
            student.group = group
            student.monthly_fee = monthly_fee
            student.payment_status = status
            student.save()
            messages.success(
                request,
                "Oâ€˜quvchi maâ€™lumotlari yangilandi." if not is_new else "Oâ€˜quvchi roâ€˜yxatga olindi.",
            )
            return redirect("students_list")
        except (ValueError, KeyError) as exc:
            messages.error(request, str(exc))
    return render(
        request, "student_form.html", {"student": student, "courses": courses, "groups": groups}
    )


@login_required
def student_create(request):
    return student_form(request, Student())


@login_required
def student_edit(request, student_id):
    return student_form(request, get_object_or_404(Student, pk=student_id))


@require_POST
@admin_required
def student_delete(request, student_id):
    get_object_or_404(Student, pk=student_id).delete()
    messages.info(request, "Oâ€˜quvchi oâ€˜chirildi.")
    return redirect("students_list")


@login_required
def courses_view(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        try:
            if form_type == "course":
                name = request.POST.get("name", "").strip()
                if not name:
                    raise ValueError("Kurs nomi majburiy.")
                if Course.objects.filter(name__iexact=name).exists():
                    raise ValueError("Bunday nomli kurs mavjud.")
                Course.objects.create(
                    name=name,
                    monthly_fee=parse_nonnegative_float(request.POST.get("monthly_fee"), "Kurs narxi"),
                    description=request.POST.get("description", "").strip(),
                )
                messages.success(request, "Yangi kurs qoâ€˜shildi.")
            elif form_type == "group":
                name = request.POST.get("group_name", "").strip()
                if not name:
                    raise ValueError("Guruh nomi majburiy.")
                course = get_object_or_404(Course, pk=int(request.POST["course_id"]))
                teacher_value = request.POST.get("teacher_id")
                teacher = get_object_or_404(Teacher, pk=int(teacher_value)) if teacher_value else None
                StudyGroup.objects.create(
                    name=name,
                    schedule_info=request.POST.get("schedule_info", "").strip(),
                    course=course,
                    teacher=teacher,
                )
                messages.success(request, "Yangi guruh yaratildi.")
            else:
                raise ValueError("Forma turi notoâ€˜gâ€˜ri.")
        except (ValueError, KeyError) as exc:
            messages.error(request, str(exc))
        except IntegrityError:
            messages.error(request, "Maâ€™lumotni saqlab boâ€˜lmadi.")
        return redirect("courses_view")
    return render(
        request,
        "courses.html",
        {
            "courses": Course.objects.all(),
            "groups": StudyGroup.objects.select_related("course", "teacher").annotate(
                student_count=Count("students")
            ),
            "teachers": Teacher.objects.filter(status="active"),
        },
    )


@require_POST
@admin_required
def course_delete(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if course.groups.exists() or course.students.exists():
        messages.error(request, "Bu kursda guruh yoki oâ€˜quvchilar bor, avval ularni oâ€˜zgartiring.")
    else:
        course.delete()
        messages.info(request, "Kurs oâ€˜chirildi.")
    return redirect("courses_view")


@require_POST
@admin_required
def group_delete(request, group_id):
    group = get_object_or_404(StudyGroup, pk=group_id)
    if group.students.exists() or group.lessons.exists():
        messages.error(request, "Bu guruhda oâ€˜quvchi yoki darslar bor, avval ularni oâ€˜zgartiring.")
    else:
        group.delete()
        messages.info(request, "Guruh oâ€˜chirildi.")
    return redirect("courses_view")


@login_required
def attendance_view(request):
    if request.method == "POST":
        try:
            group = get_object_or_404(StudyGroup, pk=int(request.POST["group_id"]))
            lesson_date_value = request.POST.get("lesson_date", "")
            lesson_date = (
                datetime.strptime(lesson_date_value, "%Y-%m-%d").date()
                if lesson_date_value
                else timezone.localdate()
            )
            existing = Lesson.objects.filter(group=group, lesson_date=lesson_date).first()
            if existing:
                messages.error(request, "Bu guruh uchun shu sana boâ€˜yicha dars allaqachon ochilgan.")
                return redirect("mark_attendance", lesson_id=existing.id)
            teacher_value = request.POST.get("teacher_id")
            teacher = get_object_or_404(Teacher, pk=int(teacher_value)) if teacher_value else None
            lesson = Lesson.objects.create(
                group=group,
                teacher=teacher,
                lesson_date=lesson_date,
                topic=request.POST.get("topic", "").strip(),
            )
            messages.success(request, "Dars ochildi, davomatni belgilashingiz mumkin.")
            return redirect("mark_attendance", lesson_id=lesson.id)
        except (ValueError, KeyError) as exc:
            messages.error(request, str(exc) or "Dars maâ€™lumotlari notoâ€˜gâ€˜ri.")
    return render(
        request,
        "attendance.html",
        {
            "groups": StudyGroup.objects.select_related("course"),
            "teachers": Teacher.objects.filter(status="active"),
            "lessons": Lesson.objects.select_related("group", "teacher"),
            "now_date": timezone.localdate().strftime("%Y-%m-%d"),
        },
    )


@login_required
def mark_attendance(request, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related("group"), pk=lesson_id)
    students = Student.objects.filter(group=lesson.group)
    existing = {record.student_id: record for record in AttendanceRecord.objects.filter(lesson=lesson)}
    if request.method == "POST":
        with transaction.atomic():
            for student in students:
                status = request.POST.get(f"status_{student.id}", "present")
                if status not in ("present", "late", "absent"):
                    status = "present"
                AttendanceRecord.objects.update_or_create(
                    student=student,
                    lesson=lesson,
                    defaults={"status": status, "recorded_at": timezone.now()},
                )
        messages.success(request, "Davomat saqlandi.")
        return redirect("attendance_view")
    return render(
        request,
        "mark_attendance.html",
        {"lesson": lesson, "students": students, "existing": existing},
    )


@require_POST
@admin_required
def lesson_delete(request, lesson_id):
    get_object_or_404(Lesson, pk=lesson_id).delete()
    messages.info(request, "Dars va unga bogâ€˜liq davomat yozuvlari oâ€˜chirildi.")
    return redirect("attendance_view")


@admin_required
def payroll_view(request):
    month_key = request.GET.get("month") or request.POST.get("month_key") or timezone.localdate().strftime("%Y-%m")
    try:
        datetime.strptime(month_key, "%Y-%m")
    except ValueError:
        messages.error(request, "Oy formati notoâ€˜gâ€˜ri.")
        month_key = timezone.localdate().strftime("%Y-%m")

    if request.method == "POST":
        try:
            teacher = get_object_or_404(Teacher, pk=int(request.POST["teacher_id"]))
            bonus = parse_nonnegative_float(request.POST.get("bonus"), "Bonus")
            deductions = parse_nonnegative_float(request.POST.get("deductions"), "Jarima")
            base_salary, total_payable, _ = calculate_teacher_month_salary(
                teacher, month_key, bonus=bonus, deductions=deductions
            )
            record, _ = SalaryRecord.objects.get_or_create(
                teacher=teacher, month_key=month_key
            )
            record.base_salary = base_salary
            record.bonus = bonus
            record.deductions = deductions
            record.total_payable = total_payable
            if request.POST.get("action") == "mark_paid":
                record.is_paid = True
                record.paid_at = timezone.now()
                message = f"{teacher.full_name} uchun oylik toâ€˜langan deb belgilandi."
            else:
                message = f"{teacher.full_name} uchun oylik hisoblandi."
            record.save()
            messages.success(request, message)
            return redirect(f"{request.path}?month={month_key}")
        except (ValueError, KeyError) as exc:
            messages.error(request, str(exc))

    records = {record.teacher_id: record for record in SalaryRecord.objects.filter(month_key=month_key)}
    rows = []
    for teacher in Teacher.objects.all():
        base_calc, total_calc, lessons_count = calculate_teacher_month_salary(teacher, month_key)
        record = records.get(teacher.id)
        rows.append(
            {
                "teacher": teacher,
                "lessons_count": lessons_count,
                "base_salary": record.base_salary if record else base_calc,
                "bonus": record.bonus if record else 0.0,
                "deductions": record.deductions if record else 0.0,
                "total_payable": record.total_payable if record else total_calc,
                "is_paid": record.is_paid if record else False,
            }
        )
    return render(request, "payroll.html", {"rows": rows, "month_key": month_key})


def permission_denied(request, exception=None):
    return render(request, "errors/403.html", status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    return render(request, "errors/500.html", status=500)
