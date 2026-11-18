from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SchoolDashboard(models.Model):
    _name = 'school.dashboard'
    _description = 'Dashboard'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    user_id = fields.Many2one(
        'res.users', string='Owner', required=True, index=True,
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    group_ids = fields.Many2many(
        'res.groups', string='Shared With',
        help='Groups allowed to view this dashboard in addition to the owner.')
    item_ids = fields.One2many(
        'school.dashboard.item', 'dashboard_id', string='Items')
    item_count = fields.Integer(compute='_compute_item_count')

    @api.depends('item_ids')
    def _compute_item_count(self):
        counts = dict(self.env['school.dashboard.item']._read_group(
            [('dashboard_id', 'in', self.ids)], ['dashboard_id'], ['__count']))
        for dashboard in self:
            dashboard.item_count = counts.get(dashboard, 0)

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'school_dashboard.dashboard_action',
            'name': self.name,
            'params': {'dashboard_id': self.id},
        }

    def get_dashboard_data(self, date_from=None, date_to=None):
        self.ensure_one()
        self.check_access('read')
        items = self.item_ids.filtered('active').sorted(
            key=lambda item: (item.sequence, item.id))
        return {
            'id': self.id,
            'name': self.name,
            'items': [
                item._get_item_data(date_from=date_from, date_to=date_to)
                for item in items
            ],
        }

    def set_item_order(self, item_ids):
        self.ensure_one()
        self.check_access('write')
        items = self.item_ids
        allowed = set(items.ids)
        ordered = []
        seen = set()
        for raw_id in item_ids:
            item_id = int(raw_id)
            if item_id not in allowed:
                raise UserError(
                    _("You can only reorder the items of this dashboard."))
            if item_id not in seen:
                seen.add(item_id)
                ordered.append(item_id)
        ordered.extend(item.id for item in items if item.id not in seen)
        for index, item_id in enumerate(ordered, start=1):
            items.browse(item_id).write({'sequence': index * 10})
        return True
