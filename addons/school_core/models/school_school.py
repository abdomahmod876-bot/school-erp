from odoo import _, api, fields, models


class SchoolSchool(models.Model):
    _name = 'school.school'
    _description = 'School'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        tracking=True,
        help='Short unique code. Generated from the school name when left empty.')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    logo = fields.Image(max_width=256, max_height=256)
    phone = fields.Char()
    email = fields.Char()
    website = fields.Char()
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    country_id = fields.Many2one(
        'res.country', string='Country',
        default=lambda self: self.env.company.country_id)
    established_date = fields.Date()
    motto = fields.Char()
    grading_system = fields.Selection(
        selection=[
            ('percentage', 'Percentage'),
            ('points', 'Points'),
            ('letters', 'Letters'),
        ],
        string='Grading System', required=True, default='percentage')
    pass_mark = fields.Float(
        default=50.0,
        help='Default pass mark used when a grade or subject does not define its own.')
    branch_ids = fields.One2many('school.branch', 'school_id', string='Branches')
    branch_count = fields.Integer(compute='_compute_branch_count')
    active = fields.Boolean(default=True)
    note = fields.Html()

    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id)',
        'The school code must be unique per company.',
    )

    @api.depends('branch_ids')
    def _compute_branch_count(self):
        for school in self:
            school.branch_count = len(school.branch_ids)

    @api.model
    def _generate_code_from_name(self, name):
        words = [word for word in name.split() if any(char.isalpha() for char in word)]
        if not words:
            return 'SCH'
        if len(words) == 1:
            return words[0][:4].upper()
        return ''.join(word[0] for word in words).upper()[:6]

    @api.model
    def _unique_code(self, base, company_id, exclude_id=None):
        school_model = self.sudo()
        code = base
        counter = 2
        domain = [('code', '=', code), ('company_id', '=', company_id)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        while school_model.search_count(domain):
            code = '%s%d' % (base, counter)
            counter += 1
            domain[0] = ('code', '=', code)
        return code

    @api.onchange('name')
    def _onchange_name_generate_code(self):
        if self.name and not self.code:
            base = self._generate_code_from_name(self.name)
            company = self.company_id or self.env.company
            self.code = self._unique_code(base, company.id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') and vals.get('name'):
                company = vals.get('company_id') or self.env.company.id
                base = self._generate_code_from_name(vals['name'])
                vals['code'] = self._unique_code(base, company)
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals and not vals['code']:
            for school in self:
                name = vals.get('name') or school.name
                base = self._generate_code_from_name(name) if name else 'SCH'
                school.write(dict(vals, code=self._unique_code(
                    base, school.company_id.id, exclude_id=school.id)))
            return True
        return super().write(vals)

    def action_open_branches(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Branches'),
            'res_model': 'school.branch',
            'view_mode': 'list,form',
            'domain': [('school_id', '=', self.id)],
            'context': {'default_school_id': self.id},
        }
