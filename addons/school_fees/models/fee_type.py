from odoo import fields, models


class SchoolFeeType(models.Model):
    _name = 'school.fee.type'
    _inherit = ['school.mixin']
    _description = 'Fee Type'
    _order = 'code, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    category = fields.Selection(
        selection=[
            ('tuition', 'Tuition'),
            ('registration', 'Registration'),
            ('books', 'Books & Materials'),
            ('uniform', 'Uniform'),
            ('transport', 'Transport'),
            ('activity', 'Activities'),
            ('exam', 'Exams'),
            ('other', 'Other'),
        ],
        required=True, default='tuition')
    default_amount = fields.Float(digits=(16, 2))
    description = fields.Text()
    active = fields.Boolean(default=True)

    _code_school_uniq = models.Constraint(
        'UNIQUE(code, school_id)',
        'The fee type code must be unique per school.',
    )
    _name_school_uniq = models.Constraint(
        'UNIQUE(name, school_id)',
        'The fee type name must be unique per school.',
    )
