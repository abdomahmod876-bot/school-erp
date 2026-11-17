from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolTeacher(models.Model):
    _name = 'school.teacher'
    _inherit = ['school.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Teacher'
    _order = 'name'

    reference = fields.Char(
        string='Teacher No.', default='New', copy=False,
        readonly=True, index=True, tracking=True)
    name = fields.Char(required=True, tracking=True, index=True)
    image = fields.Image(max_width=512, max_height=512)
    gender = fields.Selection(
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
        ],
        required=True)
    birth_date = fields.Date()
    age = fields.Integer(compute='_compute_age')
    national_id = fields.Char(string='National ID', copy=False)
    nationality_id = fields.Many2one('res.country', string='Nationality')
    email = fields.Char()
    phone = fields.Char()
    street = fields.Char()
    city = fields.Char()

    hire_date = fields.Date(default=fields.Date.context_today)
    user_id = fields.Many2one(
        'res.users', string='User Account',
        domain="[('share', '=', False)]",
        help='Internal user account used by the teacher to log in.')
    qualification = fields.Char()
    specialization = fields.Char()
    contract_type = fields.Selection(
        selection=[
            ('full_time', 'Full Time'),
            ('part_time', 'Part Time'),
            ('hourly', 'Hourly'),
        ],
        required=True, default='full_time')
    subject_ids = fields.Many2many(
        'school.subject', 'school_teacher_subject_rel',
        'teacher_id', 'subject_id', string='Subjects',
        domain="[('school_id', '=', school_id)]")
    state = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('on_leave', 'On Leave'),
            ('terminated', 'Terminated'),
        ],
        required=True, default='active', tracking=True, index=True)
    note = fields.Html()
    active = fields.Boolean(default=True)

    _reference_uniq = models.Constraint(
        'UNIQUE(reference)',
        'The teacher number must be unique.',
    )
    _user_uniq = models.Constraint(
        'UNIQUE(user_id)',
        'This user account is already linked to another teacher.',
    )

    @api.depends('birth_date')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for teacher in self:
            if teacher.birth_date:
                teacher.age = int((today - teacher.birth_date).days // 365.25)
            else:
                teacher.age = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference') or vals.get('reference') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('school.teacher') or 'New'
        return super().create(vals_list)

    @api.constrains('subject_ids', 'school_id')
    def _check_subjects_school(self):
        for teacher in self:
            wrong_subjects = teacher.subject_ids.filtered(
                lambda subject: subject.school_id != teacher.school_id)
            if wrong_subjects:
                raise ValidationError(_(
                    'These subjects do not belong to the teacher school: %(subjects)s',
                    subjects=', '.join(wrong_subjects.mapped('name'))))

    def action_set_active(self):
        self.write({'state': 'active'})

    def action_set_on_leave(self):
        self.write({'state': 'on_leave'})

    def action_terminate(self):
        self.write({'state': 'terminated'})
