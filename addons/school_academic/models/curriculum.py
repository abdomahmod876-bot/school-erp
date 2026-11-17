from odoo import fields, models


class SchoolCurriculum(models.Model):
    _name = 'school.curriculum'
    _inherit = ['school.mixin']
    _description = 'School Curriculum'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char()
    description = fields.Text()
    active = fields.Boolean(default=True)

    _name_school_uniq = models.Constraint(
        'UNIQUE(name, school_id)',
        'The curriculum name must be unique per school.',
    )
