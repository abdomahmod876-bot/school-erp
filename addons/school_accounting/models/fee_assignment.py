from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolFeeAssignment(models.Model):
    _inherit = 'school.fee.assignment'

    invoice_ids = fields.One2many(
        'account.move', 'school_fee_assignment_id', string='Invoices',
        readonly=True)
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', compute='_compute_invoice',
        store=True, copy=False)
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    invoice_state = fields.Selection(
        related='invoice_id.state', string='Invoice Status')

    @api.depends('invoice_ids')
    def _compute_invoice(self):
        for assignment in self:
            assignment.invoice_id = assignment.invoice_ids[:1]

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for assignment in self:
            assignment.invoice_count = len(assignment.invoice_ids)

    def write(self, vals):
        if 'line_ids' in vals:
            invoiced = self.filtered('invoice_ids')
            if invoiced:
                raise UserError(_(
                    'The fee lines of an invoiced fee plan cannot be modified. '
                    'Reset the invoice first.'))
        return super().write(vals)

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(
                _('Only confirmed fee plans can be invoiced.'))
        if self.invoice_ids:
            raise UserError(
                _('This fee plan already has an invoice.'))
        fee_types = self.line_ids.fee_type_id
        missing = fee_types.filtered(lambda fee_type: not fee_type.income_account_id)
        if missing:
            raise UserError(_(
                'Set an income account on the fee types: %(types)s.',
                types=', '.join(missing.mapped('display_name'))))
        partner = self.student_id._get_fee_partner()
        invoice_lines = [(0, 0, {
            'name': '%s - %s' % (line.fee_type_id.code, line.fee_type_id.name),
            'quantity': 1.0,
            'price_unit': line.amount,
            'account_id': line.fee_type_id.income_account_id.id,
            'tax_ids': [(6, 0, [])],
        }) for line in self.line_ids]
        invoice = self.env['account.move'].with_company(
            self.school_id.company_id).create({
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_origin': self.reference,
                'school_fee_assignment_id': self.id,
                'invoice_line_ids': invoice_lines,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
        }

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(
                _('No invoice is linked to this fee plan.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_cancel(self):
        for assignment in self:
            posted = assignment.invoice_ids.filtered(
                lambda invoice: invoice.state == 'posted')
            if posted:
                raise UserError(_(
                    'Reset or cancel the posted invoices before cancelling '
                    'the fee plan: %(invoices)s.',
                    invoices=', '.join(posted.mapped('name'))))
        result = super().action_cancel()
        self.invoice_ids.unlink()
        return result


class SchoolFeeAssignmentLine(models.Model):
    _inherit = 'school.fee.assignment.line'

    @api.constrains('amount', 'fee_type_id', 'due_date')
    def _check_invoice_lock(self):
        for line in self:
            if line.assignment_id.invoice_ids:
                raise ValidationError(_(
                    'The fee plan is already invoiced. Reset the invoice before '
                    'changing its fee lines.'))
