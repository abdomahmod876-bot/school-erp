from odoo import fields, models


class SchoolSubject(models.Model):
    _name = 'school.subject'
    _inherit = ['school.mixin']
    _description = 'School Subject'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char()
    subject_type = fields.Selection(
        selection=[
            ('core', 'Core'),
            ('optional', 'Optional'),
            ('activity', 'Activity'),
        ],
        string='Type', required=True, default='core')
    description = fields.Text()
    active = fields.Boolean(default=True)

    _name_school_uniq = models.Constraint(
        'UNIQUE(name, school_id)',
        'The subject name must be unique per school.',
    )
