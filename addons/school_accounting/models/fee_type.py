from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolFeeType(models.Model):
    _inherit = 'school.fee.type'

    income_account_id = fields.Many2one(
        'account.account', string='Income Account',
        domain="[('account_type', 'in', ('income', 'income_other'))]",
        help='Revenue account used on the invoices generated from this fee type.')

    @api.constrains('income_account_id', 'school_id')
    def _check_income_account_company(self):
        for fee_type in self:
            account = fee_type.income_account_id
            if account and fee_type.school_id.company_id not in account.company_ids:
                raise ValidationError(_(
                    'The income account %(account)s does not belong to the company '
                    'of the school.', account=account.display_name))
