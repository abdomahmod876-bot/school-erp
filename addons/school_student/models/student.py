from odoo import api, fields, models


class SchoolStudent(models.Model):
    _name = 'school.student'
    _inherit = ['school.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Student'
    _order = 'name'

    reference = fields.Char(
        string='Student No.', default='New', copy=False,
        readonly=True, index=True, tracking=True)
    name = fields.Char(required=True, tracking=True, index=True)
    image = fields.Image(max_width=512, max_height=512)
    gender = fields.Selection(
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
        ],
        required=True, tracking=True)
    birth_date = fields.Date()
    age = fields.Integer(compute='_compute_age')
    blood_group = fields.Selection(
        selection=[
            ('a+', 'A+'), ('a-', 'A-'),
            ('b+', 'B+'), ('b-', 'B-'),
            ('ab+', 'AB+'), ('ab-', 'AB-'),
            ('o+', 'O+'), ('o-', 'O-'),
        ],
        string='Blood Group')
    national_id = fields.Char(string='National ID', copy=False, tracking=True)
    nationality_id = fields.Many2one('res.country', string='Nationality')
    email = fields.Char()
    phone = fields.Char()
    street = fields.Char()
    city = fields.Char()
    admission_date = fields.Date(default=fields.Date.context_today)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('graduated', 'Graduated'),
            ('withdrawn', 'Withdrawn'),
        ],
        required=True, default='active', tracking=True, index=True)
    user_id = fields.Many2one(
        'res.users', string='Portal User',
        domain="[('share', '=', True)]",
        help='Portal user linked to this student, used by the student portal.')
    guardian_ids = fields.One2many(
        'school.student.guardian', 'student_id', string='Guardians')
    primary_guardian_id = fields.Many2one(
        'res.partner', string='Primary Guardian',
        compute='_compute_primary_guardian')
    note = fields.Html()
    active = fields.Boolean(default=True)

    _reference_uniq = models.Constraint(
        'UNIQUE(reference)',
        'The student number must be unique.',
    )

    @api.depends('birth_date')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for student in self:
            if student.birth_date:
                student.age = int((today - student.birth_date).days // 365.25)
            else:
                student.age = 0

    @api.depends('guardian_ids.is_primary', 'guardian_ids.partner_id')
    def _compute_primary_guardian(self):
        for student in self:
            student.primary_guardian_id = student.guardian_ids.filtered('is_primary')[:1].partner_id

    @api.depends('name', 'reference')
    def _compute_display_name(self):
        for student in self:
            if student.reference and student.reference != 'New':
                student.display_name = f"{student.reference} - {student.name}"
            else:
                student.display_name = student.name or ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference') or vals.get('reference') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('school.student') or 'New'
        return super().create(vals_list)

    def action_activate(self):
        self.write({'state': 'active'})

    def action_graduate(self):
        self.write({'state': 'graduated'})

    def action_withdraw(self):
        self.write({'state': 'withdrawn'})
