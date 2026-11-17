from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestSchoolAccounting(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(su=True)
        cls.income_account = cls.company_data['default_account_revenue']
        cls.school = cls.env['school.school'].create({
            'name': 'Accounting Test School',
            'code': 'ATS',
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
            'name': 'Grade 5',
            'stage_id': cls.stage.id,
        })
        cls.section = cls.env['school.section'].create({
            'name': 'A',
            'grade_id': cls.grade.id,
            'academic_year_id': cls.year.id,
        })
        cls.student = cls.env['school.student'].create({
            'name': 'Yara Adel',
            'gender': 'female',
            'school_id': cls.school.id,
        })
        cls.env['school.enrollment'].create({
            'student_id': cls.student.id,
            'section_id': cls.section.id,
        })
        cls.tuition = cls.env['school.fee.type'].create({
            'name': 'Tuition',
            'code': 'TUIT',
            'category': 'tuition',
            'default_amount': 1000.0,
            'school_id': cls.school.id,
            'income_account_id': cls.income_account.id,
        })
        cls.books = cls.env['school.fee.type'].create({
            'name': 'Books',
            'code': 'BOOK',
            'category': 'books',
            'default_amount': 200.0,
            'school_id': cls.school.id,
            'income_account_id': cls.income_account.id,
        })
        cls.structure = cls.env['school.fee.structure'].create({
            'name': 'Grade 5 Fees 2026/2027',
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

    def _make_assignment(self, confirm=True):
        assignment = self.env['school.fee.assignment'].create({
            'school_id': self.school.id,
            'student_id': self.student.id,
            'academic_year_id': self.year.id,
            'structure_id': self.structure.id,
        })
        if confirm:
            assignment.action_confirm()
        return assignment

    def _make_invoice(self, assignment, post=False):
        action = assignment.action_create_invoice()
        invoice = self.env['account.move'].browse(action['res_id'])
        if post:
            invoice.action_post()
        return invoice

    def _line_for(self, assignment, fee_type):
        return assignment.line_ids.filtered(
            lambda line: line.fee_type_id == fee_type)

    def test_create_invoice_from_fee_plan(self):
        assignment = self._make_assignment()
        invoice = self._make_invoice(assignment)
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(invoice.state, 'draft')
        self.assertEqual(invoice.school_fee_assignment_id, assignment)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        self.assertAlmostEqual(invoice.amount_total, 1200.0)
        self.assertTrue(all(
            line.account_id == self.income_account
            for line in invoice.invoice_line_ids))
        self.assertEqual(assignment.invoice_id, invoice)
        self.assertEqual(assignment.invoice_count, 1)
        self.assertEqual(
            invoice.partner_id, self.student.accounting_partner_id)
        self.assertTrue(invoice.partner_id.customer_rank)

    def test_create_invoice_requires_income_account(self):
        self.books.income_account_id = False
        assignment = self._make_assignment()
        with self.assertRaises(UserError):
            assignment.action_create_invoice()

    def test_create_invoice_requires_confirmed_plan(self):
        assignment = self._make_assignment(confirm=False)
        with self.assertRaises(UserError):
            assignment.action_create_invoice()

    def test_second_invoice_is_blocked(self):
        assignment = self._make_assignment()
        self._make_invoice(assignment)
        with self.assertRaises(UserError):
            assignment.action_create_invoice()

    def test_fee_lines_are_locked_after_invoice(self):
        assignment = self._make_assignment()
        self._make_invoice(assignment)
        with self.assertRaises(ValidationError):
            assignment.line_ids[0].write({'amount': 999.0})
            self.env.flush_all()
        with self.assertRaises(UserError):
            assignment.write({'line_ids': [(0, 0, {
                'fee_type_id': self.tuition.id,
                'amount': 10.0,
            })]})

    def test_cancel_removes_draft_invoice(self):
        assignment = self._make_assignment()
        self._make_invoice(assignment)
        assignment.action_cancel()
        self.assertEqual(assignment.state, 'cancelled')
        self.assertFalse(assignment.invoice_ids)

    def test_cancel_blocked_with_posted_invoice(self):
        assignment = self._make_assignment()
        self._make_invoice(assignment, post=True)
        with self.assertRaises(UserError):
            assignment.action_cancel()

    def test_payment_posted_to_accounting(self):
        assignment = self._make_assignment()
        invoice = self._make_invoice(assignment, post=True)
        tuition_line = self._line_for(assignment, self.tuition)
        books_line = self._line_for(assignment, self.books)
        payment_1 = self.env['school.fee.payment'].create({
            'line_id': tuition_line.id,
            'amount': 1000.0,
            'method': 'bank_transfer',
        })
        payment_2 = self.env['school.fee.payment'].create({
            'line_id': books_line.id,
            'amount': 200.0,
            'method': 'bank_transfer',
        })
        payment_1.action_post_account_payment()
        payment_2.action_post_account_payment()
        self.assertTrue(payment_1.account_payment_id)
        self.assertTrue(payment_2.account_payment_id)
        self.assertAlmostEqual(invoice.amount_residual, 0.0)
        self.assertIn(invoice.payment_state, ('in_payment', 'paid'))
        self.assertEqual(assignment.payment_state, 'paid')

    def test_payment_requires_posted_invoice(self):
        assignment = self._make_assignment()
        self._make_invoice(assignment)
        payment = self.env['school.fee.payment'].create({
            'line_id': self._line_for(assignment, self.tuition).id,
            'amount': 100.0,
            'method': 'bank_transfer',
        })
        with self.assertRaises(UserError):
            payment.action_post_account_payment()

    def test_delete_accounting_payment_is_blocked(self):
        assignment = self._make_assignment()
        self._make_invoice(assignment, post=True)
        payment = self.env['school.fee.payment'].create({
            'line_id': self._line_for(assignment, self.tuition).id,
            'amount': 1000.0,
            'method': 'bank_transfer',
        })
        payment.action_post_account_payment()
        with self.assertRaises(UserError):
            payment.unlink()
