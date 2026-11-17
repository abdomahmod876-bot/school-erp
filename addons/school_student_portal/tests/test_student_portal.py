from datetime import date

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install')
class TestSchoolStudentPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Student Portal School',
            'code': 'SPS',
        })
        cls.year = cls.env['school.academic.year'].create({
            'name': '2026/2027',
            'date_start': date(2026, 9, 1),
            'date_end': date(2027, 6, 30),
            'school_id': cls.school.id,
        })
        stage = cls.env['school.stage'].create({
            'name': 'Primary',
            'school_id': cls.school.id,
        })
        grade = cls.env['school.grade'].create({
            'name': 'Grade 5',
            'stage_id': stage.id,
        })
        cls.section = cls.env['school.section'].create({
            'name': 'A',
            'grade_id': grade.id,
            'academic_year_id': cls.year.id,
        })
        cls.subject = cls.env['school.subject'].create({
            'name': 'Mathematics',
            'school_id': cls.school.id,
        })
        cls.period = cls.env['school.period'].create({
            'name': 'First Period',
            'school_id': cls.school.id,
            'start_time': 8.0,
            'end_time': 9.0,
        })
        cls.student_user = cls.env['res.users'].create({
            'name': 'Omar Hany',
            'login': 'school_student',
            'password': 'school_student',
            'group_ids': [Command.set([
                cls.env.ref('school_core.group_school_student').id])],
            'school_ids': [Command.set([cls.school.id])],
        })
        cls.student = cls.env['school.student'].create({
            'name': 'Omar Hany',
            'gender': 'male',
            'school_id': cls.school.id,
            'state': 'active',
            'user_id': cls.student_user.id,
        })
        cls.other_student = cls.env['school.student'].create({
            'name': 'Yara Ali',
            'gender': 'female',
            'school_id': cls.school.id,
            'state': 'active',
        })
        cls.env['school.enrollment'].create({
            'student_id': cls.student.id,
            'section_id': cls.section.id,
            'state': 'active',
        })
        fee_type = cls.env['school.fee.type'].create({
            'name': 'Tuition',
            'code': 'TUI',
            'school_id': cls.school.id,
        })
        assignment = cls.env['school.fee.assignment'].create({
            'student_id': cls.student.id,
            'academic_year_id': cls.year.id,
            'school_id': cls.school.id,
        })
        cls.env['school.fee.assignment.line'].create({
            'assignment_id': assignment.id,
            'fee_type_id': fee_type.id,
            'amount': 750.0,
        })
        assignment.action_confirm()
        timetable = cls.env['school.timetable'].create({
            'section_id': cls.section.id,
        })
        cls.env['school.timetable.slot'].create({
            'timetable_id': timetable.id,
            'day_of_week': '1',
            'period_id': cls.period.id,
            'subject_id': cls.subject.id,
        })
        timetable.action_publish()

    def test_student_dashboard(self):
        self.authenticate('school_student', 'school_student')
        response = self.url_open('/my/student')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Omar Hany', response.text)
        self.assertIn('Mathematics', response.text)
        self.assertIn('750.00', response.text)

    def test_student_cannot_open_other_student(self):
        self.authenticate('school_student', 'school_student')
        response = self.url_open(f'/my/children/{self.other_student.id}')
        self.assertEqual(response.status_code, 404)

    def test_portal_home_lists_student_card(self):
        self.authenticate('school_student', 'school_student')
        response = self.url_open('/my/home')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/my/student', response.text)
