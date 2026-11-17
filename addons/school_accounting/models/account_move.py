from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    school_fee_assignment_id = fields.Many2one(
        'school.fee.assignment', string='Fee Plan',
        index=True, copy=False, readonly=True, ondelete='set null')

    def action_open_fee_assignment(self):
        self.ensure_one()
        if not self.school_fee_assignment_id:
            raise UserError(
                _('This invoice is not linked to a fee plan.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fee Plan'),
            'res_model': 'school.fee.assignment',
            'res_id': self.school_fee_assignment_id.id,
            'view_mode': 'form',
        }
