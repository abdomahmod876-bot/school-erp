from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestSchoolTimetable(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Timetable Test School',
            'code': 'TMS',
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
            'name': 'Grade 4',
            'stage_id': cls.stage.id,
        })
        cls.section = cls.env['school.section'].create({
            'name': 'A',
            'grade_id': cls.grade.id,
            'academic_year_id': cls.year.id,
        })
        cls.subject = cls.env['school.subject'].create({
            'name': 'Science',
            'school_id': cls.school.id,
        })
        cls.teacher = cls.env['school.teacher'].create({
            'name': 'Hany Mostafa',
            'gender': 'male',
            'school_id': cls.school.id,
            'subject_ids': [(6, 0, [cls.subject.id])],
        })
        cls.period_1 = cls.env['school.period'].create({
            'name': 'Period 1',
            'school_id': cls.school.id,
            'start_time': 8.0,
            'end_time': 8.75,
        })
        cls.period_2 = cls.env['school.period'].create({
            'name': 'Period 2',
            'school_id': cls.school.id,
            'start_time': 9.0,
            'end_time': 9.75,
        })
        cls.timetable = cls.env['school.timetable'].create({
            'section_id': cls.section.id,
        })
        cls.slot = cls.env['school.timetable.slot'].create({
            'timetable_id': cls.timetable.id,
            'day_of_week': '0',
            'period_id': cls.period_1.id,
            'subject_id': cls.subject.id,
            'teacher_id': cls.teacher.id,
            'room': 'Lab 1',
        })

    def _create_other_section(self, name='B'):
        return self.env['school.section'].create({
            'name': name,
            'grade_id': self.grade.id,
            'academic_year_id': self.year.id,
        })

    def test_slot_inherits_timetable_scope(self):
        self.assertEqual(self.slot.section_id, self.section)
        self.assertEqual(self.slot.school_id, self.school)
        self.assertEqual(self.slot.academic_year_id, self.year)
        self.assertEqual(self.timetable.slot_count, 1)
        self.assertEqual(self.teacher.weekly_hours, 0.75)

    def test_teacher_cannot_be_double_booked(self):
        other_timetable = self.env['school.timetable'].create({
            'section_id': self._create_other_section().id,
        })
        with self.assertRaises(ValidationError):
            self.env['school.timetable.slot'].create({
                'timetable_id': other_timetable.id,
                'day_of_week': '0',
                'period_id': self.period_1.id,
                'subject_id': self.subject.id,
                'teacher_id': self.teacher.id,
            })

    def test_subject_must_be_taught_by_teacher(self):
        other_subject = self.env['school.subject'].create({
            'name': 'Art',
            'school_id': self.school.id,
        })
        with self.assertRaises(ValidationError):
            self.env['school.timetable.slot'].create({
                'timetable_id': self.timetable.id,
                'day_of_week': '1',
                'period_id': self.period_2.id,
                'subject_id': other_subject.id,
                'teacher_id': self.teacher.id,
            })

    def test_section_period_is_unique(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.timetable.slot'].create({
                    'timetable_id': self.timetable.id,
                    'day_of_week': '0',
                    'period_id': self.period_1.id,
                    'subject_id': self.subject.id,
                })
                self.env.flush_all()

    def test_publish_requires_slots(self):
        empty_timetable = self.env['school.timetable'].create({
            'section_id': self._create_other_section('C').id,
        })
        with self.assertRaises(UserError):
            empty_timetable.action_publish()

    def test_publish_and_reset_draft(self):
        self.assertEqual(self.timetable.state, 'draft')
        self.timetable.action_publish()
        self.assertEqual(self.timetable.state, 'published')
        self.timetable.action_reset_draft()
        self.assertEqual(self.timetable.state, 'draft')

    def test_all_week_days_are_accepted(self):
        for day in ('1', '2', '3', '4', '5', '6'):
            slot = self.env['school.timetable.slot'].create({
                'timetable_id': self.timetable.id,
                'day_of_week': day,
                'period_id': self.period_1.id,
                'subject_id': self.subject.id,
                'teacher_id': self.teacher.id,
            })
            self.assertEqual(slot.day_of_week, day)
        self.assertEqual(self.timetable.slot_count, 7)

    def test_weekly_hours_accumulate(self):
        self.env['school.timetable.slot'].create({
            'timetable_id': self.timetable.id,
            'day_of_week': '1',
            'period_id': self.period_2.id,
            'subject_id': self.subject.id,
            'teacher_id': self.teacher.id,
        })
        self.assertAlmostEqual(self.teacher.weekly_hours, 1.5)
