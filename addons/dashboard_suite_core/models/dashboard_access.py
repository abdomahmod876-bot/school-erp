from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DashboardSuiteAccess(models.Model):
    _name = 'dashboard.suite.access'
    _description = 'Dashboard Sharing'
    _order = 'dashboard_id, id'

    dashboard_id = fields.Many2one(
        'dashboard.suite', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', ondelete='cascade', index=True)
    group_id = fields.Many2one('res.groups', ondelete='cascade', index=True)
    access_level = fields.Selection(
        selection=[
            ('viewer', 'Viewer'),
            ('editor', 'Editor'),
            ('admin', 'Administrator'),
        ],
        default='viewer', required=True)

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            dashboard_id = vals.get('dashboard_id')
            if dashboard_id:
                self.env['dashboard.suite'].browse(
                    dashboard_id)._check_editable('admin')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('dashboard_id'):
            self.env['dashboard.suite'].browse(
                vals['dashboard_id'])._check_editable('admin')
        for entry in self:
            entry.dashboard_id._check_editable('admin')
        return super().write(vals)

    def unlink(self):
        for entry in self:
            entry.dashboard_id._check_editable('admin')
        return super().unlink()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.constrains('dashboard_id', 'user_id', 'group_id', 'access_level')
    def _check_target(self):
        for entry in self:
            if bool(entry.user_id) == bool(entry.group_id):
                raise ValidationError(_(
                    'A sharing entry must target exactly one user or one group.'))

    @api.constrains('dashboard_id', 'user_id', 'group_id')
    def _check_duplicate(self):
        for entry in self:
            domain = [
                ('dashboard_id', '=', entry.dashboard_id.id),
                ('id', '!=', entry.id),
            ]
            if entry.user_id:
                domain.append(('user_id', '=', entry.user_id.id))
            else:
                domain.append(('group_id', '=', entry.group_id.id))
            if self.search_count(domain):
                raise ValidationError(_(
                    'This dashboard is already shared with %s.',
                    entry.user_id.name or entry.group_id.name))
