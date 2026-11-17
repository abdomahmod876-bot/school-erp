from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolLibraryMember(models.Model):
    _name = 'school.library.member'
    _description = 'Library Member'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    card_number = fields.Char(
        string='Card No.', default='New', copy=False,
        readonly=True, index=True)
    member_type = fields.Selection(
        selection=[
            ('student', 'Student'),
            ('teacher', 'Teacher'),
        ],
        required=True, default='student')
    student_id = fields.Many2one(
        'school.student', string='Student', ondelete='cascade', index=True)
    teacher_id = fields.Many2one(
        'school.teacher', string='Teacher', ondelete='cascade', index=True)
    school_id = fields.Many2one(
        'school.school', compute='_compute_school', store=True, index=True)
    join_date = fields.Date(
        required=True, default=fields.Date.context_today)
    loan_ids = fields.One2many(
        'school.library.loan', 'member_id', string='Loans')
    loan_count = fields.Integer(compute='_compute_loan_count')
    active_loan_count = fields.Integer(compute='_compute_loan_count')
    note = fields.Text()
    active = fields.Boolean(default=True)

    _card_uniq = models.Constraint(
        'UNIQUE(card_number)',
        'The library card number must be unique.',
    )
    _student_uniq = models.Constraint(
        'UNIQUE(student_id)',
        'The student is already registered as a library member.',
    )
    _teacher_uniq = models.Constraint(
        'UNIQUE(teacher_id)',
        'The teacher is already registered as a library member.',
    )

    @api.depends('member_type', 'student_id.name', 'student_id.reference',
                 'teacher_id.name', 'teacher_id.reference')
    def _compute_name(self):
        for member in self:
            if member.member_type == 'student' and member.student_id:
                member.name = member.student_id.display_name
            elif member.member_type == 'teacher' and member.teacher_id:
                member.name = member.teacher_id.display_name
            else:
                member.name = 'New Member'

    @api.depends('student_id.school_id', 'teacher_id.school_id')
    def _compute_school(self):
        for member in self:
            member.school_id = (
                member.student_id.school_id or member.teacher_id.school_id)

    @api.depends('loan_ids.state')
    def _compute_loan_count(self):
        for member in self:
            loans = member.loan_ids
            member.loan_count = len(loans)
            member.active_loan_count = len(loans.filtered(
                lambda loan: loan.state == 'borrowed'))

    @api.constrains('member_type', 'student_id', 'teacher_id')
    def _check_member_target(self):
        for member in self:
            if member.member_type == 'student':
                if not member.student_id or member.teacher_id:
                    raise ValidationError(_(
                        'A student member must be linked to a student only.'))
            elif not member.teacher_id or member.student_id:
                raise ValidationError(_(
                    'A teacher member must be linked to a teacher only.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('card_number', 'New') == 'New':
                vals['card_number'] = (
                    self.env['ir.sequence'].next_by_code('school.library.member')
                    or 'New')
        return super().create(vals_list)
