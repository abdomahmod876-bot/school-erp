from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolMixin(models.AbstractModel):
    _name = 'school.mixin'
    _description = 'School Scoping Mixin'

    school_id = fields.Many2one(
        'school.school', string='School', required=True,
        index=True, ondelete='restrict')
    branch_id = fields.Many2one(
        'school.branch', string='Branch', index=True,
        ondelete='restrict', domain="[('school_id', '=', school_id)]")

    @api.onchange('school_id')
    def _onchange_school_id(self):
        if self.branch_id and self.branch_id.school_id != self.school_id:
            self.branch_id = False

    @api.constrains('school_id', 'branch_id')
    def _check_branch_belongs_to_school(self):
        for record in self:
            if record.branch_id and record.branch_id.school_id != record.school_id:
                raise ValidationError(
                    _('The branch %(branch)s does not belong to the school %(school)s.',
                      branch=record.branch_id.display_name,
                      school=record.school_id.display_name))
