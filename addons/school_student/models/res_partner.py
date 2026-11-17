from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_school_guardian = fields.Boolean(string='School Guardian')
    guardian_occupation = fields.Char(string='Occupation')
    student_guardian_ids = fields.One2many(
        'school.student.guardian', 'partner_id',
        string='Students')
