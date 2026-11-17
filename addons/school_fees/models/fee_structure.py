from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolFeeStructure(models.Model):
    _name = 'school.fee.structure'
    _inherit = ['school.mixin']
    _description = 'Fee Structure'
    _order = 'academic_year_id desc, grade_id'

    name = fields.Char(required=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', string='Academic Year', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    grade_id = fields.Many2one(
        'school.grade', string='Grade', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    line_ids = fields.One2many(
        'school.fee.structure.line', 'structure_id', string='Fee Lines')
    assignment_ids = fields.One2many(
        'school.fee.assignment', 'structure_id', string='Student Fees')
    total_amount = fields.Float(compute='_compute_total_amount', digits=(16, 2))
    note = fields.Text()
    active = fields.Boolean(default=True)

    _year_grade_uniq = models.Constraint(
        'UNIQUE(academic_year_id, grade_id)',
        'A fee structure already exists for this grade and academic year.',
    )

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for structure in self:
            structure.total_amount = sum(structure.line_ids.mapped('amount'))

    @api.constrains('grade_id', 'academic_year_id', 'school_id')
    def _check_scope(self):
        for structure in self:
            if structure.grade_id.school_id != structure.school_id:
                raise ValidationError(
                    _('The grade does not belong to the selected school.'))
            if structure.academic_year_id.school_id != structure.school_id:
                raise ValidationError(
                    _('The academic year does not belong to the selected school.'))

    def action_assign_to_students(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(
                _('Add the fee lines before assigning the structure to students.'))
        sections = self.env['school.section'].search([
            ('grade_id', '=', self.grade_id.id),
            ('academic_year_id', '=', self.academic_year_id.id),
        ])
        if not sections:
            raise UserError(
                _('There are no sections for this grade in the selected academic year.'))
        enrollments = self.env['school.enrollment'].search([
            ('section_id', 'in', sections.ids),
            ('academic_year_id', '=', self.academic_year_id.id),
            ('state', '=', 'active'),
        ])
        if not enrollments:
            raise UserError(_('There are no active enrollments for this grade.'))
        already_assigned = self.env['school.fee.assignment'].search([
            ('academic_year_id', '=', self.academic_year_id.id),
        ]).student_id
        created = self.env['school.fee.assignment']
        for enrollment in enrollments:
            if enrollment.student_id in already_assigned:
                continue
            created |= self.env['school.fee.assignment'].create({
                'school_id': self.school_id.id,
                'branch_id': self.branch_id.id,
                'student_id': enrollment.student_id.id,
                'academic_year_id': self.academic_year_id.id,
                'structure_id': self.id,
                'line_ids': [(0, 0, {
                    'fee_type_id': line.fee_type_id.id,
                    'amount': line.amount,
                    'due_date': line.due_date,
                }) for line in self.line_ids],
            })
        if not created:
            raise UserError(
                _('All enrolled students already have a fee plan for this structure.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student Fees'),
            'res_model': 'school.fee.assignment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
        }


class SchoolFeeStructureLine(models.Model):
    _name = 'school.fee.structure.line'
    _description = 'Fee Structure Line'
    _rec_name = 'fee_type_id'
    _order = 'sequence, id'

    structure_id = fields.Many2one(
        'school.fee.structure', string='Fee Structure', required=True,
        ondelete='cascade', index=True)
    school_id = fields.Many2one(
        'school.school', related='structure_id.school_id',
        store=True, readonly=True, index=True)
    fee_type_id = fields.Many2one(
        'school.fee.type', string='Fee Type', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    sequence = fields.Integer(default=10)
    amount = fields.Float(required=True, digits=(16, 2))
    due_date = fields.Date()

    _structure_fee_type_uniq = models.Constraint(
        'UNIQUE(structure_id, fee_type_id)',
        'The fee type is already included in this structure.',
    )

    @api.onchange('fee_type_id')
    def _onchange_fee_type_id(self):
        if self.fee_type_id:
            self.amount = self.fee_type_id.default_amount

    @api.constrains('fee_type_id', 'structure_id')
    def _check_fee_type_school(self):
        for line in self:
            if line.fee_type_id.school_id != line.structure_id.school_id:
                raise ValidationError(_(
                    'The fee type %(fee_type)s does not belong to the school of the structure.',
                    fee_type=line.fee_type_id.display_name))

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(
                    _('The fee amount must be greater than zero.'))
