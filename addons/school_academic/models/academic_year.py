from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolAcademicYear(models.Model):
    _name = 'school.academic.year'
    _inherit = ['school.mixin']
    _description = 'Academic Year'
    _order = 'date_start desc'

    name = fields.Char(required=True, help='e.g. 2026/2027')
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    is_current = fields.Boolean(string='Current Year')
    active = fields.Boolean(default=True)
    note = fields.Text()

    _name_school_uniq = models.Constraint(
        'UNIQUE(name, school_id)',
        'The academic year name must be unique per school.',
    )
    _date_range_check = models.Constraint(
        'CHECK(date_end > date_start)',
        'The end date must be after the start date.',
    )

    @api.constrains('is_current', 'school_id')
    def _check_single_current_year(self):
        for year in self.filtered('is_current'):
            other = self.search([
                ('school_id', '=', year.school_id.id),
                ('is_current', '=', True),
                ('id', '!=', year.id),
            ], limit=1)
            if other:
                raise ValidationError(_('Only one academic year can be current per school.'))

    def action_set_current(self):
        self.ensure_one()
        self.search([
            ('school_id', '=', self.school_id.id),
            ('is_current', '=', True),
        ]).write({'is_current': False})
        self.is_current = True
