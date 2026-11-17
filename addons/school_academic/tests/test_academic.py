from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestSchoolAcademic(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Test School',
            'code': 'TST',
        })

    def _create_year(self, name, is_current=False):
        return self.env['school.academic.year'].create({
            'name': name,
            'school_id': self.school.id,
            'date_start': date(2026, 9, 1),
            'date_end': date(2027, 6, 30),
            'is_current': is_current,
        })

    def test_only_one_current_year_per_school(self):
        self._create_year('2026/2027', is_current=True)
        with self.assertRaises(ValidationError):
            self._create_year('2027/2028', is_current=True)

    def test_set_current_year_switches_previous(self):
        old = self._create_year('2025/2026', is_current=True)
        new = self._create_year('2026/2027')
        new.action_set_current()
        self.assertFalse(old.is_current)
        self.assertTrue(new.is_current)

    def test_section_display_name_and_unique(self):
        stage = self.env['school.stage'].create({
            'name': 'Primary',
            'school_id': self.school.id,
        })
        grade = self.env['school.grade'].create({
            'name': 'Grade 1',
            'stage_id': stage.id,
        })
        year = self._create_year('2026/2027', is_current=True)
        section = self.env['school.section'].create({
            'name': 'A',
            'grade_id': grade.id,
            'academic_year_id': year.id,
        })
        self.assertIn('Grade 1', section.display_name)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.section'].create({
                    'name': 'A',
                    'grade_id': grade.id,
                    'academic_year_id': year.id,
                })
                self.env.flush_all()

    def test_year_date_range(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.academic.year'].create({
                    'name': 'Bad Range',
                    'school_id': self.school.id,
                    'date_start': date(2027, 6, 30),
                    'date_end': date(2026, 9, 1),
                })
                self.env.flush_all()

    def test_subject_type_options(self):
        subject = self.env['school.subject'].create({
            'name': 'Art',
            'school_id': self.school.id,
        })
        self.assertEqual(subject.subject_type, 'core')
        for subject_type in ('core', 'optional', 'activity'):
            subject.subject_type = subject_type
            self.assertEqual(subject.subject_type, subject_type)

    def test_subject_name_unique_per_school(self):
        self.env['school.subject'].create({
            'name': 'Mathematics',
            'school_id': self.school.id,
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.subject'].create({
                    'name': 'Mathematics',
                    'school_id': self.school.id,
                })
                self.env.flush_all()

    def test_grade_subject_link(self):
        stage = self.env['school.stage'].create({
            'name': 'Primary',
            'school_id': self.school.id,
        })
        grade = self.env['school.grade'].create({
            'name': 'Grade 5',
            'stage_id': stage.id,
        })
        subject = self.env['school.subject'].create({
            'name': 'Science',
            'school_id': self.school.id,
        })
        link = self.env['school.grade.subject'].create({
            'grade_id': grade.id,
            'subject_id': subject.id,
            'weekly_hours': 5,
            'max_marks': 80.0,
            'pass_mark': 40.0,
            'elective': True,
        })
        self.assertEqual(link.school_id, self.school)
        self.assertEqual(link.weekly_hours, 5)
        self.assertTrue(link.elective)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.grade.subject'].create({
                    'grade_id': grade.id,
                    'subject_id': subject.id,
                })
                self.env.flush_all()

    def test_grade_curriculum_must_belong_to_school(self):
        other_school = self.env['school.school'].create({
            'name': 'Other School',
            'code': 'OTH',
        })
        curriculum = self.env['school.curriculum'].create({
            'name': 'Other Curriculum',
            'school_id': other_school.id,
        })
        stage = self.env['school.stage'].create({
            'name': 'Primary',
            'school_id': self.school.id,
        })
        with self.assertRaises(ValidationError):
            self.env['school.grade'].create({
                'name': 'Grade 6',
                'stage_id': stage.id,
                'curriculum_id': curriculum.id,
            })
