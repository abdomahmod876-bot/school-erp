from odoo import api, fields, models


class SchoolAccessLog(models.Model):
    _name = 'school.access.log'
    _description = 'School Access Log'
    _order = 'create_date desc, id desc'

    user_id = fields.Many2one(
        'res.users', string='User', required=True,
        ondelete='cascade', index=True)
    school_id = fields.Many2one(
        'school.school', string='School', required=True,
        ondelete='cascade', index=True)
    action = fields.Selection(
        selection=[
            ('grant', 'Granted'),
            ('revoke', 'Revoked'),
        ],
        required=True)
    granted_by = fields.Many2one(
        'res.users', string='Done By',
        default=lambda self: self.env.user)
    note = fields.Char()

    @api.depends('user_id.name', 'school_id.name', 'action')
    def _compute_display_name(self):
        actions = dict(self._fields['action'].selection)
        for log in self:
            log.display_name = '%s - %s / %s' % (
                actions.get(log.action, log.action or ''),
                log.school_id.name or '',
                log.user_id.name or '',
            )
