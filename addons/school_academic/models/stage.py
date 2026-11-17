from odoo import fields, models


class SchoolStage(models.Model):
    _name = 'school.stage'
    _inherit = ['school.mixin']
    _description = 'School Stage'
    _order = 'sequence, name'

    name = fields.Char(required=True, help='e.g. Primary, Preparatory, Secondary')
    code = fields.Char()
    sequence = fields.Integer(default=10)
    grade_ids = fields.One2many('school.grade', 'stage_id', string='Grades')
    active = fields.Boolean(default=True)

    _name_school_uniq = models.Constraint(
        'UNIQUE(name, school_id)',
        'The stage name must be unique per school.',
    )
