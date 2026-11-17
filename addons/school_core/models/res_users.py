from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    school_ids = fields.Many2many(
        'school.school', 'school_user_school_rel', 'user_id', 'school_id',
        string='Allowed Schools',
        help='Schools this user is allowed to work on. '
             'Role groups such as teacher or parent are restricted to these schools.')
    branch_ids = fields.Many2many(
        'school.branch', 'school_user_branch_rel', 'user_id', 'branch_id',
        string='Allowed Branches')
    default_school_id = fields.Many2one('school.school', string='Default School')
    default_branch_id = fields.Many2one('school.branch', string='Default Branch')

    @api.onchange('default_school_id')
    def _onchange_default_school_id(self):
        if self.default_school_id:
            if self.default_school_id not in self.school_ids:
                self.school_ids = [(4, self.default_school_id.id)]
            if self.default_branch_id and self.default_branch_id.school_id != self.default_school_id:
                self.default_branch_id = False

    @api.onchange('default_branch_id')
    def _onchange_default_branch_id(self):
        branch = self.default_branch_id
        if not branch:
            return
        if branch.school_id not in self.school_ids:
            self.school_ids = [(4, branch.school_id.id)]
        if branch not in self.branch_ids:
            self.branch_ids = [(4, branch.id)]
        if not self.default_school_id:
            self.default_school_id = branch.school_id

    @api.constrains('school_ids', 'branch_ids')
    def _check_branch_scope(self):
        for user in self:
            if user.branch_ids and not user.school_ids:
                raise ValidationError(
                    _('Select at least one school before assigning branches to %s.', user.name))
            invalid = user.branch_ids.filtered(lambda b: b.school_id not in user.school_ids)
            if invalid:
                raise ValidationError(
                    _('These branches do not belong to the schools of %(user)s: %(branches)s',
                      user=user.name,
                      branches=', '.join(invalid.mapped('display_name'))))

    @api.constrains('default_school_id', 'school_ids')
    def _check_default_school(self):
        for user in self:
            if user.default_school_id and user.default_school_id not in user.school_ids:
                raise ValidationError(
                    _('The default school of %s must be one of the allowed schools.', user.name))

    @api.constrains('default_branch_id', 'branch_ids')
    def _check_default_branch(self):
        for user in self:
            if user.default_branch_id and user.default_branch_id not in user.branch_ids:
                raise ValidationError(
                    _('The default branch of %s must be one of the allowed branches.', user.name))
