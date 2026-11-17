from werkzeug.exceptions import NotFound

from odoo import http
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


def _format_hour(value):
    hours, minutes = divmod(int(round(value * 60)), 60)
    return '%02d:%02d' % (hours, minutes)


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
