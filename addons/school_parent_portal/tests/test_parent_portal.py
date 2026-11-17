from datetime import date
import json

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install')
class TestSchoolParentPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Parent Portal School',
            'code': 'PPS',
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
        cls.teacher = cls.env['school.teacher'].create({
            'name': 'Mona Fathy',
            'gender': 'female',
            'school_id': cls.school.id,
        })
        cls.parent_user = cls.env['res.users'].create({
            'name': 'Hany Ibrahim',
            'login': 'school_parent',
            'password': 'school_parent',
            'group_ids': [Command.set([
                cls.env.ref('school_core.group_school_parent').id])],
            'school_ids': [Command.set([cls.school.id])],
        })
        cls.student = cls.env['school.student'].create({
            'name': 'Omar Hany',
            'gender': 'male',
            'school_id': cls.school.id,
            'state': 'active',
        })
        cls.env['school.student.guardian'].create({
            'student_id': cls.student.id,
            'partner_id': cls.parent_user.partner_id.id,
            'is_primary': True,
        })
        other_parent = cls.env['res.partner'].create({'name': 'Other Parent'})
        cls.other_student = cls.env['school.student'].create({
            'name': 'Yara Ali',
            'gender': 'female',
            'school_id': cls.school.id,
            'state': 'active',
        })
        cls.env['school.student.guardian'].create({
            'student_id': cls.other_student.id,
            'partner_id': other_parent.id,
            'is_primary': True,
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
        cls.assignment = cls.env['school.fee.assignment'].create({
            'student_id': cls.student.id,
            'academic_year_id': cls.year.id,
            'school_id': cls.school.id,
        })
        cls.env['school.fee.assignment.line'].create({
            'assignment_id': cls.assignment.id,
            'fee_type_id': fee_type.id,
            'amount': 1000.0,
        })
        cls.assignment.action_confirm()
        session = cls.env['school.attendance.session'].create({
            'date': date(2026, 10, 1),
            'section_id': cls.section.id,
            'school_id': cls.school.id,
        })
        session.action_load_students()
        session.action_done()
        exam = cls.env['school.exam'].create({
            'name': 'Midterm',
            'exam_type': 'midterm',
            'school_id': cls.school.id,
            'academic_year_id': cls.year.id,
            'section_ids': [Command.set([cls.section.id])],
            'date_start': date(2026, 10, 10),
            'date_end': date(2026, 10, 12),
        })
        schedule = cls.env['school.exam.schedule'].create({
            'exam_id': exam.id,
            'subject_id': cls.subject.id,
            'date': date(2026, 10, 10),
            'start_time': 9.0,
            'end_time': 10.0,
            'max_marks': 100.0,
            'pass_mark': 50.0,
        })
        cls.env['school.exam.result'].create({
            'schedule_id': schedule.id,
            'student_id': cls.student.id,
            'score': 85.0,
        })
        exam.action_publish_results()
        timetable = cls.env['school.timetable'].create({
            'section_id': cls.section.id,
        })
        cls.env['school.timetable.slot'].create({
            'timetable_id': timetable.id,
            'day_of_week': '0',
            'period_id': cls.period.id,
            'subject_id': cls.subject.id,
            'teacher_id': cls.teacher.id,
            'room': '12',
        })
        timetable.action_publish()
        cls.announcement = cls.env['school.announcement'].create({
            'name': 'Second Term Schedule',
            'body': '<p>The second term starts next Sunday.</p>',
            'audience': 'guardians',
            'school_id': cls.school.id,
        })
        cls.announcement.action_publish()

    def test_children_page_lists_guarded_students(self):
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open('/my/children')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Omar Hany', response.text)
        self.assertNotIn('Yara Ali', response.text)

    def test_child_dashboard_shows_fees_results_timetable(self):
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open(f'/my/children/{self.student.id}')
        self.assertEqual(response.status_code, 200)
        for expected in ('Omar Hany', '2026/2027', 'Mathematics', 'Mona Fathy',
                         '1000.00'):
            self.assertIn(expected, response.text)

    def test_other_parent_child_is_not_found(self):
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open(f'/my/children/{self.other_student.id}')
        self.assertEqual(response.status_code, 404)

    def test_progress_page_renders(self):
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open(f'/my/children/{self.student.id}/progress')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Progress tracker', response.text)
        self.assertIn('school-progress-app', response.text)
        self.assertIn(
            f'/school/parent/api/children/{self.student.id}/progress',
            response.text)

    def test_progress_api_returns_child_summary(self):
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open(
            f'/school/parent/api/children/{self.student.id}/progress',
            data=json.dumps({
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {},
            }),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()['result']
        self.assertEqual(payload['student']['name'], 'Omar Hany')
        self.assertEqual(payload['level']['stage'], 'Primary')
        self.assertEqual(payload['level']['grade'], 'Grade 5')
        self.assertEqual(payload['level']['section'], 'A')
        self.assertEqual(payload['level']['academic_year'], '2026/2027')
        academics = payload['academics']
        self.assertEqual(academics['average_percentage'], 85.0)
        self.assertEqual(academics['level'], 'Very Good')
        self.assertEqual(academics['published_results'], 1)
        self.assertEqual(academics['passed'], 1)
        self.assertEqual(academics['failed'], 0)
        self.assertEqual(academics['attention'], [])
        self.assertEqual(academics['subjects'][0]['name'], 'Mathematics')
        self.assertEqual(academics['subjects'][0]['average_percentage'], 85.0)
        self.assertEqual(academics['trend'][0]['exam'], 'Midterm')
        self.assertEqual(academics['trend'][0]['average_percentage'], 85.0)
        attendance = payload['attendance']
        self.assertEqual(attendance['total'], 1)
        self.assertEqual(attendance['present'], 1)
        self.assertEqual(attendance['rate'], 100.0)
        fees = payload['fees']
        self.assertEqual(fees['total'], 1000.0)
        self.assertEqual(fees['paid'], 0.0)
        self.assertEqual(fees['balance'], 1000.0)
        self.assertEqual(fees['state'], 'not_paid')

    def test_progress_api_hides_other_parents_child(self):
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open(
            f'/school/parent/api/children/{self.other_student.id}/progress',
            data=json.dumps({
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {},
            }),
            headers={'Content-Type': 'application/json'},
        )
        body = response.json()
        self.assertNotIn('result', body)
        self.assertIn('NotFound', json.dumps(body))

    def test_progress_api_flags_low_performance(self):
        self.env['school.exam.result'].search([
            ('student_id', '=', self.student.id),
        ]).score = 40.0
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open(
            f'/school/parent/api/children/{self.student.id}/progress',
            data=json.dumps({
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {},
            }),
            headers={'Content-Type': 'application/json'},
        )
        academics = response.json()['result']['academics']
        self.assertEqual(academics['average_percentage'], 40.0)
        self.assertEqual(academics['level'], 'Needs Support')
        self.assertEqual(academics['failed'], 1)
        self.assertTrue(academics['attention'])

    def test_notifications_page_shows_sent_messages(self):
        self.announcement.action_notify_guardians()
        self.announcement.notification_ids.action_send()
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open('/my/notifications')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Second Term Schedule', response.text)

    def test_portal_home_lists_children_card(self):
        self.authenticate('school_parent', 'school_parent')
        response = self.url_open('/my/home')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/my/children', response.text)
