from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DOMAIN_OPERATORS = {
    '=', '!=', '>', '>=', '<', '<=', 'in', 'not in', 'like', 'not like',
    'ilike', 'not ilike', 'child_of', 'parent_of',
}
FILTER_FIELD_TYPES = {
    'date': ('date', 'datetime'),
    'selection': ('selection',),
    'many2one': ('many2one',),
}


class DashboardSuiteFilter(models.Model):
    _name = 'dashboard.suite.filter'
    _description = 'Dashboard Filter'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    dashboard_id = fields.Many2one(
        'dashboard.suite', required=True, ondelete='cascade', index=True)
    filter_type = fields.Selection(
        selection=[
            ('date', 'Date'),
            ('selection', 'Selection'),
            ('many2one', 'Relation'),
        ],
        default='date', required=True)
    field_id = fields.Many2one(
        'ir.model.fields', string='Field',
        domain="[('store', '=', True), "
               "('ttype', 'in', ['date', 'datetime', 'selection', 'many2one'])]")
    operator = fields.Selection(
        selection=[
            ('=', 'Equals'),
            ('!=', 'Not Equals'),
            ('>=', 'Greater or Equal'),
            ('<=', 'Less or Equal'),
            ('in', 'In'),
            ('not in', 'Not In'),
            ('child_of', 'Child Of'),
        ],
        default='=', required=True)
    default_value = fields.Json(default=dict)
    is_required = fields.Boolean()
    sequence = fields.Integer(default=10)

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            dashboard_id = vals.get('dashboard_id')
            if dashboard_id:
                self.env['dashboard.suite'].browse(
                    dashboard_id)._check_editable('editor')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('dashboard_id'):
            self.env['dashboard.suite'].browse(
                vals['dashboard_id'])._check_editable('editor')
        for dashboard_filter in self:
            dashboard_filter.dashboard_id._check_editable('editor')
        return super().write(vals)

    def unlink(self):
        for dashboard_filter in self:
            dashboard_filter.dashboard_id._check_editable('editor')
        return super().unlink()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.constrains('filter_type', 'field_id', 'operator')
    def _check_filter_configuration(self):
        for dashboard_filter in self:
            field = dashboard_filter.sudo().field_id
            if not field:
                raise ValidationError(_(
                    'Select a field for filter "%s".', dashboard_filter.name))
            if not field.store:
                raise ValidationError(_(
                    'The field "%s" cannot be used in a filter because it is '
                    'not stored.', field.field_description))
            allowed_types = FILTER_FIELD_TYPES[dashboard_filter.filter_type]
            if field.ttype not in allowed_types:
                raise ValidationError(_(
                    'The field "%(field)s" cannot be used for a %(type)s '
                    'filter.', field=field.field_description,
                    type=dict(self._fields['filter_type'].selection).get(
                        dashboard_filter.filter_type)))
            if dashboard_filter.operator not in DOMAIN_OPERATORS:
                raise ValidationError(_(
                    'Unsupported filter operator "%s".', dashboard_filter.operator))
