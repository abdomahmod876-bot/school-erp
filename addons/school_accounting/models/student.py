from odoo import fields, models


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    accounting_partner_id = fields.Many2one(
        'res.partner', string='Fee Invoice Partner',
        help='Customer used on the fee invoices. When empty the primary guardian '
             'or the portal user is used, otherwise a partner is created.')

    def _get_fee_partner(self):
        self.ensure_one()
        if self.accounting_partner_id:
            return self.accounting_partner_id
        partner = self.primary_guardian_id or self.user_id.partner_id
        if not partner:
            name = self.name
            if self.reference and self.reference != 'New':
                name = '%s (%s)' % (name, self.reference)
            partner = self.env['res.partner'].create({
                'name': name,
                'ref': self.reference if self.reference != 'New' else False,
                'email': self.email,
                'phone': self.phone,
                'customer_rank': 1,
                'company_id': self.school_id.company_id.id,
            })
        self.accounting_partner_id = partner
        return partner
