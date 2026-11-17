from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolFeePayment(models.Model):
    _inherit = 'school.fee.payment'

    account_payment_id = fields.Many2one(
        'account.payment', string='Accounting Payment',
        readonly=True, copy=False, ondelete='set null', index=True)
    journal_id = fields.Many2one(
        'account.journal', string='Payment Journal',
        compute='_compute_journal_id', store=True, readonly=False,
        domain="[('type', 'in', ('bank', 'cash'))]",
        help='Journal used when the payment is posted to accounting.')

    def _default_payment_journal(self):
        self.ensure_one()
        journal_type = 'cash' if self.method == 'cash' else 'bank'
        return self.env['account.journal'].search([
            ('company_id', '=', self.school_id.company_id.id),
            ('type', '=', journal_type),
        ], limit=1)

    @api.depends('method', 'school_id')
    def _compute_journal_id(self):
        for payment in self:
            payment.journal_id = payment._default_payment_journal()

    @api.constrains('journal_id', 'school_id')
    def _check_journal_company(self):
        for payment in self:
            journal = payment.journal_id
            if not journal:
                continue
            if journal.type not in ('bank', 'cash'):
                raise ValidationError(_(
                    'The payment journal %(journal)s is not a bank or cash journal.',
                    journal=journal.display_name))
            if journal.company_id != payment.school_id.company_id:
                raise ValidationError(_(
                    'The payment journal %(journal)s belongs to another company.',
                    journal=journal.display_name))

    def action_post_account_payment(self):
        for payment in self:
            if payment.account_payment_id:
                raise UserError(
                    _('This payment is already posted to accounting.'))
            journal = payment.journal_id or payment._default_payment_journal()
            if not journal:
                raise UserError(_(
                    'Select a payment journal before posting to accounting.'))
            invoice = payment.assignment_id.invoice_id
            if not invoice or invoice.state != 'posted':
                raise UserError(_(
                    'Create and post the fee invoice of the fee plan before '
                    'posting the payment to accounting.'))
            account_payment = self.env['account.payment'].with_company(
                invoice.company_id).create({
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': invoice.partner_id.id,
                    'amount': payment.amount,
                    'date': payment.date,
                    'journal_id': journal.id,
                    'currency_id': invoice.currency_id.id,
                    'memo': payment.reference or payment.name,
                    'payment_reference': payment.reference,
                })
            account_payment.action_post()
            payment_lines = account_payment.move_id.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
                and not line.reconciled)
            invoice_lines = invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
                and not line.reconciled)
            if not payment_lines or not invoice_lines:
                raise UserError(_(
                    'The accounting payment could not be reconciled with the '
                    'fee invoice %(invoice)s.', invoice=invoice.display_name))
            (payment_lines + invoice_lines).reconcile()
            payment.account_payment_id = account_payment
        return True

    def write(self, vals):
        posted = self.filtered('account_payment_id')
        if posted and any(field in vals for field in (
                'amount', 'date', 'method', 'reference', 'line_id', 'journal_id')):
            raise UserError(
                _('A payment posted to accounting cannot be modified.'))
        return super().write(vals)

    def unlink(self):
        if any(payment.account_payment_id for payment in self):
            raise UserError(
                _('A payment posted to accounting cannot be deleted.'))
        return super().unlink()
