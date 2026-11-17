from werkzeug.exceptions import NotFound

from odoo import fields, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

DAY_LABELS = {
    '0': 'Monday',
    '1': 'Tuesday',
    '2': 'Wednesday',
    '3': 'Thursday',
    '4': 'Friday',
    '5': 'Saturday',
    '6': 'Sunday',
}

PAYMENT_BADGES = {
    'paid': 'text-bg-success',
    'partial': 'text-bg-warning',
    'not_paid': 'text-bg-secondary',
}

ATTENDANCE_BADGES = {
    'present': 'text-bg-success',
    'absent': 'text-bg-danger',
    'late': 'text-bg-warning',
    'excused': 'text-bg-info',
}

ATTENDANCE_KEYS = ('present', 'absent', 'late', 'excused')

ATTENDANCE_RATE_THRESHOLD = 75.0
PASS_THRESHOLD = 60.0

PERFORMANCE_LEVELS = (
    (90.0, 'Excellent', 'success'),
    (80.0, 'Very Good', 'success'),
    (70.0, 'Good', 'warning'),
    (60.0, 'Acceptable', 'warning'),
)


def _format_hour(value):
    hours, minutes = divmod(int(round(value * 60)), 60)
    return '%02d:%02d' % (hours, minutes)


def _performance_level(percentage):
    if percentage is None:
        return 'Not enough data', 'secondary'
    for threshold, label, tone in PERFORMANCE_LEVELS:
        if percentage >= threshold:
            return label, tone
    return 'Needs Support', 'danger'


class SchoolParentPortal(CustomerPortal):

    def _get_children(self):
        return request.env['school.student'].search([
            ('guardian_ids.partner_id', '=', request.env.user.partner_id.id),
            ('active', '=', True),
        ])

    def _get_child(self, student_id):
        child = self._get_children().filtered(lambda student: student.id == student_id)[:1]
        if not child:
            raise NotFound()
        return child

    def _get_own_student(self):
        return request.env['school.student'].search([
            ('user_id', '=', request.env.uid),
        ], limit=1)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'school_children_count' in counters:
            values['school_children_count'] = len(self._get_children())
        if 'school_notification_count' in counters:
            values['school_notification_count'] = request.env[
                'school.communication.message'].search_count([
                    ('partner_id', '=', request.env.user.partner_id.id),
                    ('state', '=', 'sent'),
                ])
        return values

    def _get_timetable_rows(self, enrollment):
        if not enrollment:
            return []
        timetable = request.env['school.timetable'].search([
            ('section_id', '=', enrollment.section_id.id),
            ('state', '=', 'published'),
        ], limit=1)
        rows = []
        for slot in timetable.line_ids.sorted(key=lambda line: (
                int(line.day_of_week), line.period_id.start_time)):
            rows.append({
                'day': DAY_LABELS.get(slot.day_of_week, slot.day_of_week),
                'period': slot.period_id.name,
                'time': '%s - %s' % (
                    _format_hour(slot.period_id.start_time),
                    _format_hour(slot.period_id.end_time)),
                'subject': slot.subject_id.name,
                'teacher': slot.teacher_id.name or '',
                'room': slot.room or '',
            })
        return rows

    def _prepare_child_values(self, student):
        values = self._prepare_portal_layout_values()
        enrollment = student.enrollment_ids.filtered(
            lambda line: line.state == 'active')[:1]
        fee_assignments = student.fee_assignment_ids.filtered(
            lambda assignment: assignment.state == 'confirmed')
        attendance_lines = request.env['school.attendance.line'].search([
            ('student_id', '=', student.id),
            ('session_id.state', '=', 'done'),
        ], order='date desc, id desc', limit=30)
        results = request.env['school.exam.result'].search([
            ('student_id', '=', student.id),
            ('exam_id.state', '=', 'published'),
        ], order='date desc, id desc', limit=30)
        values.update({
            'page_name': 'school_child',
            'student': student,
            'enrollment': enrollment,
            'fee_assignments': fee_assignments,
            'attendance_lines': attendance_lines,
            'results': results,
            'timetable_rows': self._get_timetable_rows(enrollment),
            'payment_labels': dict(
                request.env['school.fee.assignment']._fields['payment_state'].selection),
            'payment_badges': PAYMENT_BADGES,
            'attendance_badges': ATTENDANCE_BADGES,
            'grade_labels': dict(
                request.env['school.exam.result']._fields['grade'].selection),
        })
        return values

    def _prepare_progress_payload(self, student):
        enrollment = student.enrollment_ids.filtered(
            lambda line: line.state == 'active')[:1]
        section = enrollment.section_id
        results = request.env['school.exam.result'].search([
            ('student_id', '=', student.id),
            ('exam_id.state', '=', 'published'),
        ], order='date asc, id asc')
        attendance_lines = request.env['school.attendance.line'].search([
            ('student_id', '=', student.id),
            ('session_id.state', '=', 'done'),
        ])

        attendance_counts = {key: 0 for key in ATTENDANCE_KEYS}
        for line in attendance_lines:
            if line.state in attendance_counts:
                attendance_counts[line.state] += 1
        total_sessions = len(attendance_lines)
        attended = attendance_counts['present'] + attendance_counts['late']
        attendance_rate = (
            round(attended * 100.0 / total_sessions, 2) if total_sessions else None)

        total_score = total_max = 0.0
        passed = failed = 0
        subjects = {}
        exams = {}
        for result in results:
            total_score += result.score
            total_max += result.max_marks
            if result.passed:
                passed += 1
            else:
                failed += 1
            subject = subjects.setdefault(result.subject_id.id, {
                'name': result.subject_id.name or '',
                'results': 0,
                'score': 0.0,
                'max_marks': 0.0,
                'best_percentage': 0.0,
            })
            subject['results'] += 1
            subject['score'] += result.score
            subject['max_marks'] += result.max_marks
            subject['best_percentage'] = max(
                subject['best_percentage'], result.percentage or 0.0)
            exam = exams.setdefault(result.exam_id.id, {
                'name': result.exam_id.name or '',
                'date': fields.Date.to_string(result.date) if result.date else '',
                'score': 0.0,
                'max_marks': 0.0,
            })
            exam['score'] += result.score
            exam['max_marks'] += result.max_marks

        average = round(total_score * 100.0 / total_max, 2) if total_max else None
        level_label, level_tone = _performance_level(average)

        subject_rows = []
        for subject in subjects.values():
            subject_rows.append({
                'name': subject['name'],
                'results': subject['results'],
                'average_percentage': (
                    round(subject['score'] * 100.0 / subject['max_marks'], 2)
                    if subject['max_marks'] else 0.0),
                'best_percentage': round(subject['best_percentage'], 2),
            })
        subject_rows.sort(key=lambda row: row['name'])

        trend = []
        for exam in exams.values():
            trend.append({
                'exam': exam['name'],
                'date': exam['date'],
                'average_percentage': (
                    round(exam['score'] * 100.0 / exam['max_marks'], 2)
                    if exam['max_marks'] else 0.0),
            })

        assignments = student.fee_assignment_ids.filtered(
            lambda assignment: assignment.state == 'confirmed')
        fees = {
            'total': round(sum(assignments.mapped('total_amount')), 2),
            'paid': round(sum(assignments.mapped('paid_amount')), 2),
            'balance': round(sum(assignments.mapped('balance')), 2),
            'state': 'not_paid',
        }
        if fees['balance'] <= 0 and fees['total'] > 0:
            fees['state'] = 'paid'
        elif fees['paid'] > 0:
            fees['state'] = 'partial'

        attention = []
        if average is not None and average < PASS_THRESHOLD:
            attention.append('Average is below the pass mark of %d%%' % PASS_THRESHOLD)
        if attendance_rate is not None and attendance_rate < ATTENDANCE_RATE_THRESHOLD:
            attention.append(
                'Attendance is below %d%%' % ATTENDANCE_RATE_THRESHOLD)
        if failed:
            attention.append('%s failed exam result(s)' % failed)

        return {
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'student': {
                'id': student.id,
                'name': student.name,
                'reference': student.reference,
                'state': student.state,
                'school': student.school_id.name or '',
            },
            'level': {
                'stage': section.grade_id.stage_id.name or '',
                'grade': section.grade_id.name or '',
                'section': section.name or '',
                'academic_year': enrollment.academic_year_id.name or '',
            },
            'attendance': dict(
                attendance_counts,
                total=total_sessions,
                rate=attendance_rate),
            'academics': {
                'average_percentage': average,
                'level': level_label,
                'level_tone': level_tone,
                'published_results': len(results),
                'passed': passed,
                'failed': failed,
                'subjects': subject_rows,
                'trend': trend,
                'attention': attention,
            },
            'fees': fees,
        }

    @http.route(['/my/children'], type='http', auth='user', website=True)
    def children(self, **kwargs):
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'school_children',
            'children': self._get_children(),
        })
        return request.render('school_parent_portal.portal_children', values)

    @http.route(['/my/children/<int:student_id>'], type='http', auth='user', website=True)
    def child(self, student_id, **kwargs):
        student = self._get_child(student_id)
        return request.render(
            'school_parent_portal.portal_child',
            self._prepare_child_values(student))

    @http.route(['/my/children/<int:student_id>/progress'],
                type='http', auth='user', website=True)
    def child_progress(self, student_id, **kwargs):
        student = self._get_child(student_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'school_child_progress',
            'student': student,
            'progress_api_url': '/school/parent/api/children/%s/progress' % student.id,
        })
        return request.render('school_parent_portal.portal_child_progress', values)

    @http.route(['/school/parent/api/children/<int:student_id>/progress'],
                type='jsonrpc', auth='user')
    def api_child_progress(self, student_id, **kwargs):
        student = self._get_child(student_id)
        return self._prepare_progress_payload(student)

    @http.route(['/my/notifications'], type='http', auth='user', website=True)
    def notifications(self, **kwargs):
        partner = request.env.user.partner_id
        children = self._get_children()
        messages = request.env['school.communication.message'].search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'sent'),
        ], order='create_date desc', limit=50)
        announcements = request.env['school.announcement'].search([
            ('state', '=', 'published'),
            ('school_id', 'in', children.school_id.ids),
            ('audience', 'in', ('all', 'guardians')),
        ], order='date_start desc', limit=20)
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'school_notifications',
            'messages': messages,
            'announcements': announcements,
        })
        return request.render('school_parent_portal.portal_notifications', values)
