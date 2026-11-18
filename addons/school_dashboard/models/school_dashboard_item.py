import logging
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

NUMERIC_TYPES = ('integer', 'float', 'monetary')
GROUPABLE_TYPES = ('many2one', 'selection', 'char', 'boolean', 'integer')
DATE_TYPES = ('date', 'datetime')
LIST_TYPES = (
    'char', 'selection', 'many2one', 'date', 'datetime',
    'integer', 'float', 'monetary', 'boolean',
)
LIST_BLACKLIST = ('id', 'display_name', 'create_uid', 'write_uid',
                  'create_date', 'write_date')


class SchoolDashboardItem(models.Model):
    _name = 'school.dashboard.item'
    _description = 'Dashboard Item'
    _order = 'sequence, id'

    dashboard_id = fields.Many2one(
        'school.dashboard', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    item_type = fields.Selection(
        selection=[
            ('tile', 'Tile'),
            ('kpi', 'KPI'),
            ('line', 'Line Chart'),
            ('bar', 'Bar Chart'),
            ('pie', 'Pie Chart'),
            ('doughnut', 'Doughnut Chart'),
            ('list', 'List'),
        ],
        default='tile', required=True)
    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain="[('transient', '=', False)]")
    measure = fields.Selection(
        selection=[
            ('count', 'Record Count'),
            ('sum', 'Sum'),
            ('avg', 'Average'),
            ('min', 'Minimum'),
            ('max', 'Maximum'),
        ],
        default='count', required=True)
    measure_field_id = fields.Many2one(
        'ir.model.fields', string='Measure Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['integer', 'float', 'monetary'])]")
    groupby_field_id = fields.Many2one(
        'ir.model.fields', string='Group By',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['many2one', 'selection', 'char', 'boolean', 'integer'])]")
    date_field_id = fields.Many2one(
        'ir.model.fields', string='Date Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['date', 'datetime'])]",
        help='Used for the dashboard date filter, monthly trends and period '
             'comparison. Charts group by month of this field when no '
             '"Group By" is set.')
    domain = fields.Char(
        string='Filter (Domain)', default='[]',
        help="Odoo domain applied to the model, e.g. [('state', '=', 'active')]. "
             "'uid' and 'user' are available for the current user.")
    limit = fields.Integer(default=10, help='Maximum number of groups or rows shown.')
    list_field_ids = fields.Many2many(
        'ir.model.fields', 'school_dashboard_item_list_field_rel',
        'item_id', 'field_id', string='List Columns',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['char', 'selection', 'many2one', 'date', "
               "'datetime', 'integer', 'float', 'monetary', 'boolean'])]")
    icon = fields.Char(default='fa-bar-chart', help='Font Awesome icon, e.g. fa-users.')
    color = fields.Char(default='#6366f1', help='Accent color in hex, e.g. #6366f1.')
    span = fields.Selection(
        selection=[
            ('3', '1/4 width'),
            ('4', '1/3 width'),
            ('6', '1/2 width'),
            ('8', '2/3 width'),
            ('12', 'Full width'),
        ],
        default='4', required=True)

    @api.constrains('measure', 'measure_field_id')
    def _check_measure_field(self):
        for item in self:
            if item.measure != 'count' and not item.measure_field_id:
                raise ValidationError(
                    _("Choose a measure field for the item '%s'.", item.name))

    def _item_kind(self):
        if self.item_type in ('tile', 'kpi'):
            return 'scalar'
        if self.item_type == 'list':
            return 'list'
        return 'chart'

    def _get_item_data(self, date_from=None, date_to=None):
        self.ensure_one()
        data = {
            'id': self.id,
            'name': self.name,
            'item_type': self.item_type,
            'kind': self._item_kind(),
            'span': int(self.span or 4),
            'icon': self.icon or '',
            'color': self.color or '#6366f1',
        }
        try:
            data.update(self._compute_payload(date_from, date_to))
        except (AccessError, UserError, ValidationError) as err:
            data['error'] = str(err)
        except Exception:
            _logger.exception('Dashboard item %s (%s) failed', self.id, self.name)
            data['error'] = _('This item could not be computed. '
                              'Check its model, fields and filter.')
        return data

    def _check_stored_fields(self):
        measure_field = self.sudo().measure_field_id
        if measure_field and not measure_field.store:
            raise UserError(_(
                "The measure field '%s' cannot be aggregated because it is "
                "not stored.", measure_field.field_description))
        groupby_field = self.sudo().groupby_field_id
        if groupby_field and not groupby_field.store:
            raise UserError(_(
                "The field '%s' cannot be used in 'Group By' because it is "
                "not stored.", groupby_field.field_description))
        date_field = self.sudo().date_field_id
        if date_field and not date_field.store:
            raise UserError(_(
                "The date field '%s' is not stored and cannot be filtered.",
                date_field.field_description))

    def _compute_payload(self, date_from, date_to):
        self.ensure_one()
        model = self.env[self.sudo().model_id.model]
        model.check_access('read')
        self._check_stored_fields()
        domain = self._apply_date_range(self._parse_domain(), date_from, date_to)
        if self.item_type == 'list':
            return self._payload_list(model, domain)
        if self._item_kind() == 'scalar':
            return self._payload_scalar(model, domain, date_from, date_to)
        return self._payload_chart(model, domain)

    # ------------------------------------------------------------------
    # Filtering helpers
    # ------------------------------------------------------------------
    def _parse_domain(self):
        self.ensure_one()
        context = {
            'uid': self.env.uid,
            'user': self.env.user,
            'today': fields.Date.context_today(self),
            'datetime': datetime,
            'timedelta': timedelta,
        }
        try:
            domain = safe_eval(self.domain or '[]', context)
        except Exception as err:
            raise UserError(
                _("Invalid filter on the item '%(item)s': %(error)s",
                  item=self.name, error=err))
        if not isinstance(domain, list):
            raise UserError(
                _("The filter of the item '%s' must be a domain list.", self.name))
        return domain

    def _apply_date_range(self, domain, date_from, date_to):
        date_field = self.sudo().date_field_id
        if not date_field:
            return domain
        fname = date_field.name
        result = list(domain)
        d_from = fields.Date.to_date(date_from) if date_from else None
        d_to = fields.Date.to_date(date_to) if date_to else None
        if d_from:
            if date_field.ttype == 'date':
                result.append((fname, '>=', d_from))
            else:
                result.append((fname, '>=', datetime.combine(d_from, time.min)))
        if d_to:
            if date_field.ttype == 'date':
                result.append((fname, '<=', d_to))
            else:
                result.append(
                    (fname, '<', datetime.combine(d_to + timedelta(days=1), time.min)))
        return result

    # ------------------------------------------------------------------
    # Scalar payload (tile / kpi)
    # ------------------------------------------------------------------
    def _aggregate(self):
        measure_field = self.sudo().measure_field_id
        if self.measure == 'count' or not measure_field:
            return '__count'
        return f'{measure_field.name}:{self.measure}'

    def _scalar_value(self, records, domain):
        rows = records._read_group(domain, [], [self._aggregate()])
        if not rows:
            return 0
        value = rows[0][0]
        return value if value is not None else 0

    def _payload_scalar(self, records, domain, date_from, date_to):
        value = self._scalar_value(records, domain)
        payload = {'value': value, 'trend': False}
        if self.sudo().date_field_id and date_from and date_to:
            d_from = fields.Date.to_date(date_from)
            d_to = fields.Date.to_date(date_to)
            if d_from and d_to:
                span_days = (d_to - d_from).days + 1
                prev_domain = self._apply_date_range(
                    self._parse_domain(),
                    d_from - timedelta(days=span_days),
                    d_from - timedelta(days=1),
                )
                previous = self._scalar_value(records, prev_domain)
                if previous:
                    change = (value - previous) / abs(previous) * 100.0
                    payload['trend'] = {
                        'direction': 'up' if change > 0 else ('down' if change < 0 else 'flat'),
                        'label': f'{change:+.1f}%',
                        'previous': previous,
                    }
        return payload

    # ------------------------------------------------------------------
    # Chart payload
    # ------------------------------------------------------------------
    def _groupby_spec(self):
        groupby_field = self.sudo().groupby_field_id
        if groupby_field:
            return groupby_field.name
        date_field = self.sudo().date_field_id
        if date_field:
            return f'{date_field.name}:month'
        return None

    def _payload_chart(self, records, domain):
        spec = self._groupby_spec()
        if not spec:
            raise UserError(
                _("The item '%s' needs a 'Group By' or a 'Date' field.", self.name))
        field = self.sudo().groupby_field_id or self.sudo().date_field_id
        model = self.env[self.sudo().model_id.model]
        limit = min(max(self.limit or 10, 1), 100)
        groups = records._read_group(domain, [spec], [self._aggregate()])
        points = []
        for row in groups:
            key = row[0]
            value = row[1] if len(row) > 1 else 0
            points.append({
                'key': key,
                'label': self._format_key(model, field, key),
                'value': value if value is not None else 0,
            })
        is_temporal = field.ttype in DATE_TYPES
        points.sort(key=lambda point: self._sort_key(point['key'], is_temporal))
        if is_temporal:
            points = points[-limit:]
        else:
            points.sort(key=lambda point: point['value'], reverse=True)
            points = points[:limit]
        return {
            'kind': 'chart',
            'labels': [point['label'] for point in points],
            'values': [point['value'] for point in points],
            'total': records.search_count(domain),
        }

    @staticmethod
    def _sort_key(key, is_temporal):
        if is_temporal:
            return key if isinstance(key, str) else str(key)
        return ''

    def _format_key(self, model, field, key):
        if field.ttype == 'boolean':
            return _('Yes') if key else _('No')
        if key is False or key is None:
            return _('Undefined')
        if field.ttype == 'many2one':
            if isinstance(key, models.BaseModel):
                try:
                    return key.display_name or f'#{key.id}'
                except AccessError:
                    return f'#{key.id}'
            if isinstance(key, (list, tuple)) and len(key) == 2:
                return key[1]
            if isinstance(key, int):
                try:
                    return self.env[field.relation].browse(key).display_name or f'#{key}'
                except AccessError:
                    return f'#{key}'
            return str(key)
        if field.ttype == 'selection':
            field_obj = model._fields.get(field.name)
            if field_obj is None:
                return str(key)
            selection = dict(field_obj._description_selection(self.env))
            return selection.get(key, str(key))
        if field.ttype in DATE_TYPES:
            if isinstance(key, str):
                key = fields.Date.to_date(key) or key
            if hasattr(key, 'strftime'):
                return key.strftime('%b %Y')
            return str(key)
        return str(key)

    # ------------------------------------------------------------------
    # List payload
    # ------------------------------------------------------------------
    def _list_columns(self):
        model = self.env[self.sudo().model_id.model]
        list_fields = self.sudo().list_field_ids
        if list_fields:
            return [
                {
                    'name': field.name,
                    'label': field.field_description,
                    'type': field.ttype,
                }
                for field in list_fields
            ]
        columns = []
        for fname, field in model._fields.items():
            if fname in LIST_BLACKLIST or not field.store:
                continue
            if field.ttype not in LIST_TYPES:
                continue
            columns.append({
                'name': fname,
                'label': field.string,
                'type': field.ttype,
            })
            if len(columns) >= 4:
                break
        return columns

    def _payload_list(self, model, domain):
        columns = self._list_columns() or [
            {'name': 'display_name', 'label': _('Name'), 'type': 'char'},
        ]
        limit = min(max(self.limit or 10, 1), 100)
        rows = model.search_read(
            domain, [column['name'] for column in columns],
            limit=limit, order='id desc')
        return {
            'kind': 'list',
            'columns': columns,
            'rows': [
                [self._format_cell(model, column, row.get(column['name']))
                 for column in columns]
                for row in rows
            ],
            'total': model.search_count(domain),
        }

    def _format_cell(self, model, column, value):
        if value is False or value is None:
            return '—'
        ttype = column['type']
        if ttype == 'many2one':
            if isinstance(value, (list, tuple)) and len(value) > 1:
                return value[1]
            return str(value)
        if ttype == 'selection':
            field = model._fields[column['name']]
            selection = dict(field._description_selection(self.env))
            return selection.get(value, str(value))
        if ttype == 'boolean':
            return _('Yes') if value else _('No')
        if ttype in ('float', 'monetary'):
            return f'{value:,.2f}'.rstrip('0').rstrip('.')
        if ttype == 'integer':
            return f'{value:,}'
        if ttype in DATE_TYPES:
            return str(value)[:10]
        return str(value)
