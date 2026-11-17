from odoo import api, fields, models


class SchoolPeriod(models.Model):
    _name = 'school.period'
    _inherit = ['school.mixin']
    _description = 'Class Period'
    _order = 'sequence, start_time'

    name = fields.Char(required=True, help='e.g. First Period')
    code = fields.Char()
    sequence = fields.Integer(default=10)
    start_time = fields.Float(required=True, help='Start time in hours, e.g. 8.5 for 08:30')
    end_time = fields.Float(required=True, help='End time in hours, e.g. 9.25 for 09:15')
    duration = fields.Float(compute='_compute_duration')
    active = fields.Boolean(default=True)

    _name_school_uniq = models.Constraint(
        'UNIQUE(name, school_id)',
        'The period name must be unique per school.',
    )
    _time_range_check = models.Constraint(
        'CHECK(end_time > start_time)',
        'The end time must be after the start time.',
    )

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for period in self:
            period.duration = period.end_time - period.start_time
