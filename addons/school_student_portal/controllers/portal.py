from odoo import http
from odoo.http import request
from odoo.addons.school_parent_portal.controllers.portal import SchoolParentPortal


class SchoolStudentPortal(SchoolParentPortal):

    def _get_portal_student(self):
        return request.env['school.student'].search([
            ('user_id', '=', request.env.uid),
        ], limit=1)

    def _get_child(self, student_id):
        own_student = self._get_portal_student()
        if own_student and own_student.id == student_id:
            return own_student
        return super()._get_child(student_id)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'school_student_count' in counters:
            values['school_student_count'] = 1 if self._get_portal_student() else 0
        return values

    @http.route(['/my/student'], type='http', auth='user', website=True)
    def student_home(self, **kwargs):
        student = self._get_portal_student()
        if not student:
            return request.redirect('/my')
        values = self._prepare_child_values(student)
        values['page_name'] = 'school_student'
        return request.render('school_parent_portal.portal_child', values)
