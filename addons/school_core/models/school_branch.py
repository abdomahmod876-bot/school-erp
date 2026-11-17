from odoo import api, fields, models


class SchoolBranch(models.Model):
    _name = 'school.branch'
    _description = 'School Branch'
    _order = 'school_id, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    school_id = fields.Many2one(
        'school.school', string='School', required=True,
        index=True, ondelete='cascade')
    manager_id = fields.Many2one('res.users', string='Branch Manager')
    phone = fields.Char()
    email = fields.Char()
    street = fields.Char()
    city = fields.Char()
    active = fields.Boolean(default=True)
    note = fields.Text()

    _code_school_uniq = models.Constraint(
        'UNIQUE(code, school_id)',
        'The branch code must be unique per school.',
    )

    @api.depends('name', 'school_id.name')
    def _compute_display_name(self):
        for branch in self:
            if branch.school_id:
                branch.display_name = f"{branch.school_id.name} / {branch.name}"
            else:
                branch.display_name = branch.name or ''
