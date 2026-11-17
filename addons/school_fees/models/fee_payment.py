from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolFeePayment(models.Model):
    _name = 'school.fee.payment'
    _description = 'Fee Payment'
    _rec_name = 'name'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Payment No.', default='New', copy=False,
        readonly=True, index=True)
    line_id = fields.Many2one(
        'school.fee.assignment.line', string='Fee Line', required=True,
        ondelete='cascade', index=True)
    assignment_id = fields.Many2one(
        'school.fee.assignment', related='line_id.assignment_id',
        store=True, readonly=True, index=True)
    student_id = fields.Many2one(
        'school.student', related='line_id.student_id',
        store=True, readonly=True, index=True)
    school_id = fields.Many2one(
        'school.school', related='line_id.school_id',
        store=True, readonly=True, index=True)
    amount = fields.Float(required=True, digits=(16, 2))
    date = fields.Date(
        default=fields.Date.context_today, required=True, index=True)
    method = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('card', 'Card'),
            ('cheque', 'Cheque'),
            ('other', 'Other'),
        ],
        required=True, default='cash')
    reference = fields.Char(help='External reference, e.g. transfer or cheque number.')
    note = fields.Text()

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        'The payment number must be unique.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('school.fee.payment')
                    or 'New')
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(
                    _('The payment amount must be greater than zero.'))

    @api.constrains('line_id', 'amount')
    def _check_line_balance(self):
        for payment in self:
            line = payment.line_id
            other_paid = sum(
                line.payment_ids.filtered(
                    lambda other: other != payment).mapped('amount'))
            if other_paid + payment.amount > line.amount:
                raise ValidationError(_(
                    'The payment exceeds the balance of the fee line %(line)s.',
                    line=line.fee_type_id.display_name))

    @api.constrains('line_id')
    def _check_assignment_state(self):
        for payment in self:
            if payment.line_id.assignment_id.state != 'confirmed':
                raise ValidationError(
                    _('Payments can only be registered on confirmed fee plans.'))
