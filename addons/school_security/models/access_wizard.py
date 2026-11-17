from odoo import _, fields, models
from odoo.exceptions import UserError


class SchoolAccessWizard(models.TransientModel):
    _name = 'school.access.wizard'
    _description = 'Bulk School Access Assignment'

    user_ids = fields.Many2many(
        'res.users', string='Users', required=True,
        domain=[('share', '=', False)])
    school_ids = fields.Many2many('school.school', string='Schools')
    branch_ids = fields.Many2many(
        'school.branch', string='Branches',
        domain="[('school_id', 'in', school_ids)]")
    action = fields.Selection(
        selection=[
            ('grant', 'Grant'),
            ('revoke', 'Revoke'),
        ],
        default='grant', required=True)

    def action_apply(self):
        self.ensure_one()
        portal_users = self.user_ids.filtered('share')
        if portal_users:
            raise UserError(_(
                'Portal users cannot be managed here: %s',
                ', '.join(portal_users.mapped('name'))))
        if not self.school_ids and not self.branch_ids:
            raise UserError(_('Select at least one school or branch.'))

        schools = self.school_ids | self.branch_ids.mapped('school_id')
        log_model = self.env['school.access.log'].sudo()

        for user in self.user_ids:
            if self.action == 'grant':
                vals = {'school_ids': [(4, school.id) for school in schools]}
                if self.branch_ids:
                    vals['branch_ids'] = [(4, branch.id) for branch in self.branch_ids]
                if not user.default_school_id and schools:
                    vals['default_school_id'] = schools[0].id
                user.write(vals)
            else:
                branches = self.branch_ids | user.branch_ids.filtered(
                    lambda branch: branch.school_id in schools)
                vals = {}
                if self.school_ids:
                    vals['school_ids'] = [(3, school.id) for school in self.school_ids]
                if branches:
                    vals['branch_ids'] = [(3, branch.id) for branch in branches]
                if user.default_school_id and user.default_school_id in schools:
                    vals['default_school_id'] = False
                if user.default_branch_id and user.default_branch_id in branches:
                    vals['default_branch_id'] = False
                if vals:
                    user.write(vals)

            log_model.create([{
                'user_id': user.id,
                'school_id': school.id,
                'action': self.action,
                'note': ', '.join(self.branch_ids.mapped('display_name')) or False,
            } for school in schools])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('School Access Updated'),
                'message': _('%s user(s) updated.', len(self.user_ids)),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
