from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolFeeAssignment(models.Model):
    _name = 'school.fee.assignment'
    _inherit = ['school.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Student Fee Plan'
    _order = 'academic_year_id desc, student_id'

    reference = fields.Char(
        string='Fee Plan No.', default='New', copy=False,
        readonly=True, index=True, tracking=True)
    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    academic_year_id = fields.Many2one(
        'school.academic.year', string='Academic Year', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    structure_id = fields.Many2one(
        'school.fee.structure', string='Fee Structure',
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id), ('academic_year_id', '=', academic_year_id)]")
    date = fields.Date(
        default=fields.Date.context_today, required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        required=True, default='draft', tracking=True, index=True)
    line_ids = fields.One2many(
        'school.fee.assignment.line', 'assignment_id', string='Fee Lines')
    total_amount = fields.Float(
        compute='_compute_amounts', store=True, digits=(16, 2))
    paid_amount = fields.Float(
        compute='_compute_amounts', store=True, digits=(16, 2))
    balance = fields.Float(
        compute='_compute_amounts', store=True, digits=(16, 2))
    payment_state = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('paid', 'Paid'),
        ],
        compute='_compute_amounts', store=True, index=True)
    note = fields.Text()

    _reference_uniq = models.Constraint(
        'UNIQUE(reference)',
        'The fee plan number must be unique.',
    )
    _student_year_uniq = models.Constraint(
        'UNIQUE(student_id, academic_year_id)',
        'A student can have only one fee plan per academic year.',
    )

    @api.depends('line_ids.amount', 'line_ids.paid_amount')
    def _compute_amounts(self):
        for assignment in self:
            total = sum(assignment.line_ids.mapped('amount'))
            paid = sum(assignment.line_ids.mapped('paid_amount'))
            assignment.total_amount = total
            assignment.paid_amount = paid
            assignment.balance = total - paid
            if total and paid >= total:
                assignment.payment_state = 'paid'
            elif paid > 0:
                assignment.payment_state = 'partial'
            else:
                assignment.payment_state = 'not_paid'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('school.fee.assignment')
                    or 'New')
            structure_id = vals.get('structure_id')
            if structure_id and not vals.get('line_ids'):
                structure = self.env['school.fee.structure'].browse(structure_id)
                vals['line_ids'] = [(0, 0, {
                    'fee_type_id': line.fee_type_id.id,
                    'amount': line.amount,
                    'due_date': line.due_date,
                }) for line in structure.line_ids]
        return super().create(vals_list)

    @api.constrains('student_id', 'school_id')
    def _check_student_school(self):
        for assignment in self:
            if assignment.student_id.school_id != assignment.school_id:
                raise ValidationError(
                    _('The student does not belong to the selected school.'))

    @api.constrains('student_id', 'academic_year_id')
    def _check_student_enrollment(self):
        for assignment in self:
            enrollment = self.env['school.enrollment'].search([
                ('student_id', '=', assignment.student_id.id),
                ('academic_year_id', '=', assignment.academic_year_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if not enrollment:
                raise ValidationError(_(
                    'The student %(student)s has no active enrollment in this academic year.',
                    student=assignment.student_id.name))

    @api.constrains('structure_id', 'academic_year_id', 'school_id')
    def _check_structure_scope(self):
        for assignment in self:
            structure = assignment.structure_id
            if not structure:
                continue
            if structure.academic_year_id != assignment.academic_year_id:
                raise ValidationError(_(
                    'The fee structure belongs to another academic year.'))
            if structure.school_id != assignment.school_id:
                raise ValidationError(_(
                    'The fee structure belongs to another school.'))

    def action_generate_lines(self):
        for assignment in self:
            if assignment.state != 'draft':
                raise UserError(
                    _('Reset the fee plan to draft before generating the lines.'))
            if not assignment.structure_id:
                raise UserError(
                    _('Select a fee structure before generating the fee lines.'))
            existing_types = assignment.line_ids.fee_type_id
            commands = [(0, 0, {
                'fee_type_id': line.fee_type_id.id,
                'amount': line.amount,
                'due_date': line.due_date,
            }) for line in assignment.structure_id.line_ids
                if line.fee_type_id not in existing_types]
            if not commands:
                raise UserError(_(
                    'The fee plan already contains all fee types of the structure.'))
            assignment.write({'line_ids': commands})

    def action_confirm(self):
        for assignment in self:
            if assignment.state != 'draft':
                raise UserError(_('Only draft fee plans can be confirmed.'))
            if not assignment.line_ids:
                raise UserError(
                    _('Add at least one fee line before confirming the fee plan.'))
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        for assignment in self:
            if assignment.paid_amount > 0:
                raise UserError(_(
                    'A fee plan with registered payments cannot be cancelled.'))
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for assignment in self:
            if assignment.paid_amount > 0:
                raise UserError(_(
                    'A fee plan with registered payments cannot be reset to draft.'))
        self.write({'state': 'draft'})

    def action_register_payment(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(
                _('Confirm the fee plan before registering payments.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'school.fee.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_assignment_id': self.id},
        }


class SchoolFeeAssignmentLine(models.Model):
    _name = 'school.fee.assignment.line'
    _description = 'Student Fee Line'
    _rec_name = 'fee_type_id'
    _order = 'due_date, id'

    assignment_id = fields.Many2one(
        'school.fee.assignment', string='Fee Plan', required=True,
        ondelete='cascade', index=True)
    school_id = fields.Many2one(
        'school.school', related='assignment_id.school_id',
        store=True, readonly=True, index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', related='assignment_id.academic_year_id',
        store=True, readonly=True, index=True)
    student_id = fields.Many2one(
        'school.student', related='assignment_id.student_id',
        store=True, readonly=True, index=True)
    fee_type_id = fields.Many2one(
        'school.fee.type', string='Fee Type', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    amount = fields.Float(required=True, digits=(16, 2))
    due_date = fields.Date()
    payment_ids = fields.One2many(
        'school.fee.payment', 'line_id', string='Payments')
    paid_amount = fields.Float(
        compute='_compute_paid_amount', store=True, digits=(16, 2))
    balance = fields.Float(
        compute='_compute_balance', store=True, digits=(16, 2))
    state = fields.Selection(
        selection=[
            ('unpaid', 'Unpaid'),
            ('partial', 'Partially Paid'),
            ('paid', 'Paid'),
        ],
        compute='_compute_balance', store=True, index=True)

    _assignment_fee_type_uniq = models.Constraint(
        'UNIQUE(assignment_id, fee_type_id)',
        'The fee type is already included in this fee plan.',
    )

    @api.depends('payment_ids.amount')
    def _compute_paid_amount(self):
        for line in self:
            line.paid_amount = sum(line.payment_ids.mapped('amount'))

    @api.depends('amount', 'paid_amount')
    def _compute_balance(self):
        for line in self:
            line.balance = line.amount - line.paid_amount
            if line.paid_amount <= 0:
                line.state = 'unpaid'
            elif line.paid_amount >= line.amount:
                line.state = 'paid'
            else:
                line.state = 'partial'

    @api.constrains('fee_type_id', 'assignment_id')
    def _check_fee_type_school(self):
        for line in self:
            if line.fee_type_id.school_id != line.assignment_id.school_id:
                raise ValidationError(_(
                    'The fee type does not belong to the school of the fee plan.'))

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(
                    _('The fee amount must be greater than zero.'))
            if line.amount < line.paid_amount:
                raise ValidationError(_(
                    'The fee amount cannot be lower than the amount already paid.'))


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    fee_assignment_ids = fields.One2many(
        'school.fee.assignment', 'student_id', string='Fee Plans')
    fee_balance = fields.Float(
        compute='_compute_fee_balance', digits=(16, 2))

    @api.depends('fee_assignment_ids.balance', 'fee_assignment_ids.state')
    def _compute_fee_balance(self):
        for student in self:
            confirmed = student.fee_assignment_ids.filtered(
                lambda assignment: assignment.state == 'confirmed')
            student.fee_balance = sum(confirmed.mapped('balance'))
