from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SchoolFeePaymentWizard(models.TransientModel):
    _name = 'school.fee.payment.wizard'
    _description = 'Register Fee Payment'

    assignment_id = fields.Many2one(
        'school.fee.assignment', string='Fee Plan', required=True,
        ondelete='cascade')
    line_id = fields.Many2one(
        'school.fee.assignment.line', string='Fee Line', required=True,
        domain="[('assignment_id', '=', assignment_id), ('state', '!=', 'paid')]")
    amount = fields.Float(required=True, digits=(16, 2))
    date = fields.Date(
        default=fields.Date.context_today, required=True)
    method = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('card', 'Card'),
            ('cheque', 'Cheque'),
            ('other', 'Other'),
        ],
        required=True, default='cash')
    reference = fields.Char()
    note = fields.Text()

    @api.onchange('line_id')
    def _onchange_line_id(self):
        if self.line_id:
            self.amount = self.line_id.balance

    def action_register_payment(self):
        self.ensure_one()
        if self.line_id.assignment_id != self.assignment_id:
            raise UserError(
                _('Select a fee line that belongs to the selected fee plan.'))
        self.env['school.fee.payment'].create({
            'line_id': self.line_id.id,
            'amount': self.amount,
            'date': self.date,
            'method': self.method,
            'reference': self.reference,
            'note': self.note,
        })
        return {'type': 'ir.actions.act_window_close'}
