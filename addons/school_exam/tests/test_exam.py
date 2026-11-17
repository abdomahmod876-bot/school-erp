from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestSchoolExam(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Exam Test School',
            'code': 'ETS',
        })
        cls.year = cls.env['school.academic.year'].create({
            'name': '2026/2027',
            'date_start': date(2026, 9, 1),
            'date_end': date(2027, 6, 30),
            'school_id': cls.school.id,
            'is_current': True,
        })
        cls.stage = cls.env['school.stage'].create({
            'name': 'Primary',
            'school_id': cls.school.id,
        })
        cls.grade = cls.env['school.grade'].create({
            'name': 'Grade 3',
            'stage_id': cls.stage.id,
        })
        cls.section_a = cls.env['school.section'].create({
            'name': 'A',
            'grade_id': cls.grade.id,
            'academic_year_id': cls.year.id,
        })
        cls.section_b = cls.env['school.section'].create({
            'name': 'B',
            'grade_id': cls.grade.id,
            'academic_year_id': cls.year.id,
        })
        cls.student_1 = cls.env['school.student'].create({
            'name': 'Mona Said',
            'gender': 'female',
            'school_id': cls.school.id,
        })
        cls.student_2 = cls.env['school.student'].create({
            'name': 'Youssef Ali',
            'gender': 'male',
            'school_id': cls.school.id,
        })
        cls.env['school.enrollment'].create([
            {'student_id': cls.student_1.id, 'section_id': cls.section_a.id},
            {'student_id': cls.student_2.id, 'section_id': cls.section_b.id},
        ])
        cls.math = cls.env['school.subject'].create({
            'name': 'Mathematics',
            'code': 'MATH',
            'school_id': cls.school.id,
        })
        cls.science = cls.env['school.subject'].create({
            'name': 'Science',
            'code': 'SCI',
            'school_id': cls.school.id,
        })
        cls.english = cls.env['school.subject'].create({
            'name': 'English',
            'code': 'ENG',
            'school_id': cls.school.id,
        })
        cls.exam = cls.env['school.exam'].create({
            'name': 'Midterm Exam 1',
            'exam_type': 'midterm',
            'school_id': cls.school.id,
            'academic_year_id': cls.year.id,
            'section_ids': [(6, 0, (cls.section_a | cls.section_b).ids)],
            'date_start': date(2026, 12, 1),
            'date_end': date(2026, 12, 10),
        })
        cls.math_line = cls.env['school.exam.schedule'].create({
            'exam_id': cls.exam.id,
            'subject_id': cls.math.id,
            'date': date(2026, 12, 2),
            'start_time': 9.0,
            'end_time': 10.5,
        })
        cls.science_line = cls.env['school.exam.schedule'].create({
            'exam_id': cls.exam.id,
            'subject_id': cls.science.id,
            'date': date(2026, 12, 5),
            'start_time': 9.0,
            'end_time': 10.0,
            'max_marks': 50.0,
            'pass_mark': 25.0,
        })

    def test_generate_results_for_all_sections(self):
        self.exam.action_generate_results()
        self.assertEqual(len(self.math_line.result_ids), 2)
        self.assertEqual(len(self.science_line.result_ids), 2)
        self.assertEqual(self.exam.result_count, 4)

    def test_grades_and_average(self):
        self.exam.action_generate_results()
        math_results = self.math_line.result_ids
        math_results[0].score = 92.0
        math_results[1].score = 65.0
        self.assertEqual(math_results[0].grade, 'a')
        self.assertTrue(math_results[0].passed)
        self.assertEqual(math_results[1].grade, 'd')
        self.assertAlmostEqual(self.math_line.average_percent, 78.5)

    def test_grade_uses_subject_max_marks(self):
        self.exam.action_generate_results()
        result = self.science_line.result_ids[0]
        result.score = 45.0
        self.assertAlmostEqual(result.percentage, 90.0)
        self.assertEqual(result.grade, 'a')
        self.assertTrue(result.passed)

    def test_score_out_of_range(self):
        self.exam.action_generate_results()
        with self.assertRaises(ValidationError):
            self.math_line.result_ids[0].score = 150.0

    def test_student_must_be_enrolled_in_exam_sections(self):
        outsider = self.env['school.student'].create({
            'name': 'Karim Fathy',
            'gender': 'male',
            'school_id': self.school.id,
        })
        with self.assertRaises(ValidationError):
            self.env['school.exam.result'].create({
                'schedule_id': self.math_line.id,
                'student_id': outsider.id,
            })

    def test_publish_requires_results(self):
        with self.assertRaises(UserError):
            self.exam.action_publish_results()
        self.exam.action_generate_results()
        self.exam.action_publish_results()
        self.assertEqual(self.exam.state, 'published')
        self.exam.action_reset_draft()
        self.assertEqual(self.exam.state, 'draft')

    def test_duplicate_schedule_subject_is_rejected(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.exam.schedule'].create({
                    'exam_id': self.exam.id,
                    'subject_id': self.math.id,
                    'date': date(2026, 12, 3),
                    'start_time': 11.0,
                    'end_time': 12.0,
                })
                self.env.flush_all()

    def test_schedule_date_must_be_within_exam_period(self):
        with self.assertRaises(ValidationError):
            self.env['school.exam.schedule'].create({
                'exam_id': self.exam.id,
                'subject_id': self.english.id,
                'date': date(2026, 12, 20),
                'start_time': 9.0,
                'end_time': 10.0,
            })

    def test_exam_type_options(self):
        for index, exam_type in enumerate(
                ('quiz', 'monthly', 'midterm', 'final', 'practical')):
            exam = self.env['school.exam'].create({
                'name': 'Type Exam %s' % exam_type,
                'exam_type': exam_type,
                'school_id': self.school.id,
                'academic_year_id': self.year.id,
                'date_start': date(2026, 12, 1),
                'date_end': date(2026, 12, 10),
            })
            self.assertEqual(exam.exam_type, exam_type)
            self.assertEqual(exam.state, 'draft')

    def test_grade_scale(self):
        self.exam.action_generate_results()
        result = self.math_line.result_ids[0]
        for score, grade in ((95.0, 'a'), (85.0, 'b'), (75.0, 'c'), (65.0, 'd'), (40.0, 'f')):
            result.score = score
            self.assertEqual(result.grade, grade)
        self.assertFalse(result.passed)
        result.score = 50.0
        self.assertTrue(result.passed)

    def test_exam_stats(self):
        self.exam.action_generate_results()
        results = self.math_line.result_ids
        results[0].score = 90.0
        results[1].score = 50.0
        self.assertEqual(self.exam.schedule_count, 2)
        self.assertEqual(self.exam.result_count, 4)
        self.assertAlmostEqual(self.exam.average_percent, 35.0)

    def test_invalid_exam_dates(self):
        with self.assertRaises(ValidationError):
            self.env['school.exam'].create({
                'name': 'Bad Dates Exam',
                'exam_type': 'quiz',
                'school_id': self.school.id,
                'academic_year_id': self.year.id,
                'date_start': date(2026, 12, 10),
                'date_end': date(2026, 12, 1),
            })

    def test_sections_must_belong_to_exam_school(self):
        other_school = self.env['school.school'].create({
            'name': 'Other Exam School',
            'code': 'OES',
        })
        other_year = self.env['school.academic.year'].create({
            'name': '2026/2027',
            'date_start': date(2026, 9, 1),
            'date_end': date(2027, 6, 30),
            'school_id': other_school.id,
        })
        other_stage = self.env['school.stage'].create({
            'name': 'Primary',
            'school_id': other_school.id,
        })
        other_grade = self.env['school.grade'].create({
            'name': 'Grade 1',
            'stage_id': other_stage.id,
        })
        other_section = self.env['school.section'].create({
            'name': 'A',
            'grade_id': other_grade.id,
            'academic_year_id': other_year.id,
        })
        with self.assertRaises(ValidationError):
            self.exam.section_ids = [(4, other_section.id)]
