from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestSchoolLibrary(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Library Test School',
            'code': 'LTS',
        })
        cls.student = cls.env['school.student'].create({
            'name': 'Omar Hany',
            'gender': 'male',
            'school_id': cls.school.id,
        })
        cls.teacher = cls.env['school.teacher'].create({
            'name': 'Mona Fathy',
            'gender': 'female',
            'school_id': cls.school.id,
        })
        cls.book = cls.env['school.library.book'].create({
            'name': 'Mathematics Grade 5',
            'isbn': '9780000000001',
            'school_id': cls.school.id,
            'copies_total': 1,
        })
        cls.member = cls.env['school.library.member'].create({
            'member_type': 'student',
            'student_id': cls.student.id,
        })

    def _loan_vals(self, **kwargs):
        values = {
            'book_id': self.book.id,
            'member_id': self.member.id,
        }
        values.update(kwargs)
        return values

    def test_member_card_number_from_sequence(self):
        self.assertNotEqual(self.member.card_number, 'New')
        self.assertEqual(self.member.school_id, self.school)

    def test_loan_flow_respects_available_copies(self):
        loan = self.env['school.library.loan'].create(self._loan_vals())
        self.assertEqual(loan.state, 'borrowed')
        self.assertNotEqual(loan.reference, 'New')
        self.assertEqual(self.book.copies_available, 0)
        self.assertEqual(self.member.active_loan_count, 1)

        with self.assertRaises(UserError):
            self.env['school.library.loan'].create(self._loan_vals())

        loan.action_return()
        self.assertEqual(loan.state, 'returned')
        self.assertEqual(self.book.copies_available, 1)
        self.assertEqual(self.member.active_loan_count, 0)

    def test_book_categories(self):
        for category in ('textbook', 'fiction', 'reference', 'periodical', 'other'):
            book = self.env['school.library.book'].create({
                'name': 'Book %s' % category,
                'isbn': 'ISBN-%s' % category,
                'category': category,
                'school_id': self.school.id,
            })
            self.assertEqual(book.category, category)

    def test_return_reset_and_lost_cycle(self):
        loan = self.env['school.library.loan'].create(self._loan_vals())
        loan.action_return()
        self.assertEqual(loan.state, 'returned')
        self.assertTrue(loan.return_date)
        self.assertEqual(self.book.copies_available, 1)

        loan.action_reset_borrowed()
        self.assertEqual(loan.state, 'borrowed')
        self.assertFalse(loan.return_date)
        self.assertEqual(self.book.copies_available, 0)

        loan.action_mark_lost()
        self.assertEqual(loan.state, 'lost')
        self.assertEqual(self.book.copies_available, 0)
        with self.assertRaises(UserError):
            loan.action_reset_borrowed()

    def test_lost_copy_is_not_available(self):
        loan = self.env['school.library.loan'].create(self._loan_vals())
        loan.action_mark_lost()
        self.assertEqual(loan.state, 'lost')
        self.assertEqual(self.book.copies_available, 0)

    def test_late_days(self):
        today = fields.Date.context_today(self.member)
        loan = self.env['school.library.loan'].create(
            self._loan_vals(
                loan_date=today - timedelta(days=10),
                due_date=today - timedelta(days=3)))
        self.assertGreaterEqual(loan.late_days, 3)

    def test_member_type_must_match_target(self):
        with self.assertRaises(ValidationError):
            self.env['school.library.member'].create({
                'member_type': 'student',
                'teacher_id': self.teacher.id,
            })
        other_student = self.env['school.student'].create({
            'name': 'Unregistered Student',
            'gender': 'female',
            'school_id': self.school.id,
        })
        with self.assertRaises(ValidationError):
            self.env['school.library.member'].create({
                'member_type': 'teacher',
                'student_id': other_student.id,
            })

    def test_member_per_student_is_unique(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.env['school.library.member'].create({
                'member_type': 'student',
                'student_id': self.student.id,
            })

    def test_teacher_member(self):
        member = self.env['school.library.member'].create({
            'member_type': 'teacher',
            'teacher_id': self.teacher.id,
        })
        self.assertEqual(member.school_id, self.school)
        self.assertIn(self.teacher.name, member.name)
