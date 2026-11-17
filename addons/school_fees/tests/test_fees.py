from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestSchoolFees(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Fees Test School',
            'code': 'FTS',
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
            'name': 'Grade 4',
            'stage_id': cls.stage.id,
        })
        cls.section = cls.env['school.section'].create({
            'name': 'A',
            'grade_id': cls.grade.id,
            'academic_year_id': cls.year.id,
        })
        cls.student_1 = cls.env['school.student'].create({
            'name': 'Hana Mostafa',
            'gender': 'female',
            'school_id': cls.school.id,
        })
        cls.student_2 = cls.env['school.student'].create({
            'name': 'Ramy Nabil',
            'gender': 'male',
            'school_id': cls.school.id,
        })
        cls.env['school.enrollment'].create([
            {'student_id': cls.student_1.id, 'section_id': cls.section.id},
            {'student_id': cls.student_2.id, 'section_id': cls.section.id},
        ])
        cls.tuition = cls.env['school.fee.type'].create({
            'name': 'Tuition',
            'code': 'TUIT',
            'category': 'tuition',
            'default_amount': 1000.0,
            'school_id': cls.school.id,
        })
        cls.books = cls.env['school.fee.type'].create({
            'name': 'Books',
            'code': 'BOOK',
            'category': 'books',
            'default_amount': 200.0,
            'school_id': cls.school.id,
        })
        cls.structure = cls.env['school.fee.structure'].create({
            'name': 'Grade 4 Fees 2026/2027',
            'school_id': cls.school.id,
            'academic_year_id': cls.year.id,
            'grade_id': cls.grade.id,
            'line_ids': [
                (0, 0, {
                    'fee_type_id': cls.tuition.id,
                    'amount': 1000.0,
                    'due_date': date(2026, 9, 15),
                }),
                (0, 0, {
                    'fee_type_id': cls.books.id,
                    'amount': 200.0,
                    'due_date': date(2026, 10, 1),
                }),
            ],
        })

    def _make_assignment(self, student=None):
        return self.env['school.fee.assignment'].create({
            'school_id': self.school.id,
            'student_id': (student or self.student_1).id,
            'academic_year_id': self.year.id,
            'structure_id': self.structure.id,
        })

    def _tuition_line(self, assignment):
        return assignment.line_ids.filtered(
            lambda line: line.fee_type_id == self.tuition)

    def _books_line(self, assignment):
        return assignment.line_ids.filtered(
            lambda line: line.fee_type_id == self.books)

    def test_assignment_created_from_structure(self):
        assignment = self._make_assignment()
        self.assertEqual(len(assignment.line_ids), 2)
        self.assertAlmostEqual(assignment.total_amount, 1200.0)
        self.assertAlmostEqual(assignment.balance, 1200.0)
        self.assertEqual(assignment.payment_state, 'not_paid')
        self.assertTrue(assignment.reference.startswith('FEE/'))

    def test_assign_structure_to_enrolled_students(self):
        action = self.structure.action_assign_to_students()
        assignments = self.env['school.fee.assignment'].search([
            ('structure_id', '=', self.structure.id),
        ])
        self.assertEqual(len(assignments), 2)
        self.assertEqual(action['res_model'], 'school.fee.assignment')
        with self.assertRaises(UserError):
            self.structure.action_assign_to_students()

    def test_payment_flow(self):
        assignment = self._make_assignment()
        assignment.action_confirm()
        tuition_line = self._tuition_line(assignment)
        books_line = self._books_line(assignment)

        self.env['school.fee.payment'].create({
            'line_id': tuition_line.id,
            'amount': 400.0,
            'method': 'cash',
        })
        self.assertAlmostEqual(tuition_line.paid_amount, 400.0)
        self.assertEqual(tuition_line.state, 'partial')
        self.assertAlmostEqual(assignment.paid_amount, 400.0)
        self.assertAlmostEqual(assignment.balance, 800.0)
        self.assertEqual(assignment.payment_state, 'partial')

        self.env['school.fee.payment'].create({
            'line_id': tuition_line.id,
            'amount': 600.0,
            'method': 'bank_transfer',
        })
        self.assertEqual(tuition_line.state, 'paid')
        self.assertAlmostEqual(assignment.paid_amount, 1000.0)
        self.assertEqual(assignment.payment_state, 'partial')

        self.env['school.fee.payment'].create({
            'line_id': books_line.id,
            'amount': 200.0,
        })
        self.assertEqual(books_line.state, 'paid')
        self.assertAlmostEqual(assignment.paid_amount, 1200.0)
        self.assertAlmostEqual(assignment.balance, 0.0)
        self.assertEqual(assignment.payment_state, 'paid')
        self.assertAlmostEqual(self.student_1.fee_balance, 0.0)

    def test_payment_exceeding_line_balance(self):
        assignment = self._make_assignment()
        assignment.action_confirm()
        tuition_line = self._tuition_line(assignment)
        with self.assertRaises(ValidationError):
            self.env['school.fee.payment'].create({
                'line_id': tuition_line.id,
                'amount': 1200.0,
            })

    def test_payment_requires_confirmed_plan(self):
        assignment = self._make_assignment()
        with self.assertRaises(ValidationError):
            self.env['school.fee.payment'].create({
                'line_id': self._tuition_line(assignment).id,
                'amount': 100.0,
            })

    def test_cancel_with_payments_is_blocked(self):
        assignment = self._make_assignment()
        assignment.action_confirm()
        self.env['school.fee.payment'].create({
            'line_id': self._tuition_line(assignment).id,
            'amount': 100.0,
        })
        with self.assertRaises(UserError):
            assignment.action_cancel()

    def test_student_without_enrollment_is_rejected(self):
        outsider = self.env['school.student'].create({
            'name': 'Dina Sherif',
            'gender': 'female',
            'school_id': self.school.id,
        })
        with self.assertRaises(ValidationError):
            self._make_assignment(student=outsider)

    def test_one_plan_per_student_and_year(self):
        self._make_assignment()
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.fee.assignment'].create({
                    'school_id': self.school.id,
                    'student_id': self.student_1.id,
                    'academic_year_id': self.year.id,
                })
                self.env.flush_all()

    def test_payment_wizard(self):
        assignment = self._make_assignment()
        assignment.action_confirm()
        tuition_line = self._tuition_line(assignment)
        wizard = self.env['school.fee.payment.wizard'].create({
            'assignment_id': assignment.id,
            'line_id': tuition_line.id,
            'amount': 150.0,
            'method': 'card',
        })
        wizard.action_register_payment()
        self.assertEqual(len(tuition_line.payment_ids), 1)
        self.assertAlmostEqual(assignment.paid_amount, 150.0)
        self.assertAlmostEqual(assignment.balance, 1050.0)

    def test_payment_method_options(self):
        assignment = self._make_assignment()
        assignment.action_confirm()
        tuition_line = self._tuition_line(assignment)
        methods = ('cash', 'bank_transfer', 'card', 'cheque', 'other')
        for method in methods:
            payment = self.env['school.fee.payment'].create({
                'line_id': tuition_line.id,
                'amount': 100.0,
                'method': method,
            })
            self.assertEqual(payment.method, method)
        self.assertAlmostEqual(tuition_line.paid_amount, 500.0)
        self.assertEqual(tuition_line.state, 'partial')
        self.assertEqual(len(tuition_line.payment_ids), len(methods))

    def test_cancel_and_reset_without_payments(self):
        assignment = self._make_assignment()
        assignment.action_cancel()
        self.assertEqual(assignment.state, 'cancelled')
        self.assertEqual(self.student_1.fee_balance, 0.0)
        assignment.action_reset_draft()
        self.assertEqual(assignment.state, 'draft')
        assignment.action_confirm()
        self.assertEqual(assignment.state, 'confirmed')

    def test_generate_lines_on_demand(self):
        assignment = self.env['school.fee.assignment'].create({
            'school_id': self.school.id,
            'student_id': self.student_1.id,
            'academic_year_id': self.year.id,
        })
        self.assertFalse(assignment.line_ids)
        with self.assertRaises(UserError):
            assignment.action_generate_lines()
        assignment.structure_id = self.structure
        assignment.action_generate_lines()
        self.assertEqual(len(assignment.line_ids), 2)
        self.assertAlmostEqual(assignment.total_amount, 1200.0)
        with self.assertRaises(UserError):
            assignment.action_generate_lines()

    def test_confirm_requires_lines(self):
        assignment = self.env['school.fee.assignment'].create({
            'school_id': self.school.id,
            'student_id': self.student_1.id,
            'academic_year_id': self.year.id,
        })
        with self.assertRaises(UserError):
            assignment.action_confirm()

    def test_register_payment_action(self):
        assignment = self._make_assignment()
        assignment.action_confirm()
        action = assignment.action_register_payment()
        self.assertEqual(action['res_model'], 'school.fee.payment.wizard')
        self.assertEqual(action['context']['default_assignment_id'], assignment.id)
        draft = self._make_assignment(self.student_2)
        with self.assertRaises(UserError):
            draft.action_register_payment()

    def test_fee_type_categories(self):
        assignment = self._make_assignment()
        self.assertEqual(
            set(assignment.line_ids.mapped('fee_type_id.category')),
            {'tuition', 'books'})
        for index, category in enumerate((
                'tuition', 'registration', 'books', 'uniform',
                'transport', 'activity', 'exam', 'other')):
            fee_type = self.env['school.fee.type'].create({
                'name': 'Fee %s' % category,
                'code': 'CAT%d' % index,
                'category': category,
                'school_id': self.school.id,
            })
            self.assertEqual(fee_type.category, category)
