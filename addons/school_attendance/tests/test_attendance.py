from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchoolAttendance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Attendance Test School',
            'code': 'ATS',
        })
        cls.year = cls.env['school.academic.year'].create({
            'name': '2026/2027',
            'date_start': '2026-09-01',
            'date_end': '2027-06-30',
            'school_id': cls.school.id,
            'is_current': True,
        })
        cls.stage = cls.env['school.stage'].create({
            'name': 'Primary',
            'school_id': cls.school.id,
        })
        cls.grade = cls.env['school.grade'].create({
            'name': 'Grade 2',
            'stage_id': cls.stage.id,
        })
        cls.section = cls.env['school.section'].create({
            'name': 'A',
            'grade_id': cls.grade.id,
            'academic_year_id': cls.year.id,
        })
        cls.student_1 = cls.env['school.student'].create({
            'name': 'Ali Hassan',
            'gender': 'male',
            'school_id': cls.school.id,
        })
        cls.student_2 = cls.env['school.student'].create({
            'name': 'Nour Adel',
            'gender': 'female',
            'school_id': cls.school.id,
        })
        cls.env['school.enrollment'].create([
            {'student_id': cls.student_1.id, 'section_id': cls.section.id},
            {'student_id': cls.student_2.id, 'section_id': cls.section.id},
        ])
        cls.period = cls.env['school.period'].create({
            'name': 'Period 1',
            'school_id': cls.school.id,
            'start_time': 8.0,
            'end_time': 8.75,
        })
        cls.session = cls.env['school.attendance.session'].create({
            'school_id': cls.school.id,
            'section_id': cls.section.id,
            'date': '2026-10-05',
            'period_id': cls.period.id,
        })

    def test_load_students_creates_lines(self):
        self.session.action_load_students()
        self.assertEqual(len(self.session.line_ids), 2)
        self.assertEqual(self.session.present_count, 2)
        self.assertEqual(self.session.absent_count, 0)

    def test_mark_all_present_and_close(self):
        self.session.action_load_students()
        self.session.line_ids[0].state = 'absent'
        self.assertEqual(self.session.absent_count, 1)
        self.session.action_mark_all_present()
        self.assertEqual(self.session.absent_count, 0)
        self.session.action_done()
        self.assertEqual(self.session.state, 'done')
        self.session.action_reset_draft()
        self.assertEqual(self.session.state, 'draft')

    def test_student_must_be_enrolled(self):
        outsider = self.env['school.student'].create({
            'name': 'Omar Tarek',
            'gender': 'male',
            'school_id': self.school.id,
        })
        with self.assertRaises(ValidationError):
            self.env['school.attendance.line'].create({
                'session_id': self.session.id,
                'student_id': outsider.id,
            })

    def test_duplicate_register_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['school.attendance.session'].create({
                'school_id': self.school.id,
                'section_id': self.section.id,
                'date': '2026-10-05',
                'period_id': self.period.id,
            })

    def test_line_state_counts(self):
        self.session.action_load_students()
        first, second = self.session.line_ids
        first.write({'state': 'late', 'remark': 'Bus delay'})
        second.state = 'excused'
        self.assertEqual(self.session.present_count, 0)
        self.assertEqual(self.session.late_count, 1)
        self.assertEqual(self.session.excused_count, 1)
        self.assertEqual(self.session.absent_count, 0)
        self.assertEqual(first.remark, 'Bus delay')
        self.assertEqual(self.session.academic_year_id, self.year)

    def test_close_requires_loaded_students(self):
        with self.assertRaises(UserError):
            self.session.action_done()

    def test_actions_blocked_after_close(self):
        self.session.action_load_students()
        self.session.action_done()
        with self.assertRaises(UserError):
            self.session.action_load_students()
        with self.assertRaises(UserError):
            self.session.action_mark_all_present()
        self.session.action_reset_draft()
        self.session.action_load_students()
        self.assertEqual(len(self.session.line_ids), 2)

    def test_session_name(self):
        self.assertIn('Grade 2 A', self.session.name)
        self.assertIn('2026-10-05', self.session.name)
        self.assertIn('Period 1', self.session.name)
