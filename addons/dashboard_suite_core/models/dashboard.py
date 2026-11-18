import base64
import csv
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .aggregation_engine import MAX_GROUPS
from .data_engine import WidgetDataEngine

_logger = logging.getLogger(__name__)

ACCESS_LEVELS = [
    ('viewer', 'Viewer'),
    ('editor', 'Editor'),
    ('admin', 'Administrator'),
]
ACCESS_LEVEL_ORDER = {'viewer': 1, 'editor': 2, 'admin': 3}
GRID_COLUMNS = 12
MAX_GRID_HEIGHT = 6
MANAGER_GROUP = 'dashboard_suite_core.group_dashboard_manager'
ADMIN_ONLY_FIELDS = {
    'user_id', 'company_ids', 'visibility', 'dashboard_type',
    'access_ids', 'is_default', 'active',
}


class DashboardSuite(models.Model):
    _name = 'dashboard.suite'
    _description = 'Dashboard'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    description = fields.Text()
    user_id = fields.Many2one(
        'res.users', string='Owner', required=True, index=True,
        default=lambda self: self.env.user)
    company_ids = fields.Many2many(
        'res.company', string='Allowed Companies',
        default=lambda self: self.env.company,
        help='Companies allowed to use this dashboard. Leave empty to allow '
             'every company the user has access to.')
    widget_ids = fields.One2many(
        'dashboard.suite.widget', 'dashboard_id', string='Widgets',
        copy=True)
    filter_ids = fields.One2many(
        'dashboard.suite.filter', 'dashboard_id', string='Filters',
        copy=True)
    access_ids = fields.One2many(
        'dashboard.suite.access', 'dashboard_id', string='Sharing',
        copy=False)
    dashboard_type = fields.Selection(
        selection=[('dynamic', 'Dynamic'), ('predefined', 'Predefined')],
        default='dynamic', required=True)
    visibility = fields.Selection(
        selection=[('private', 'Private'), ('shared', 'Shared')],
        default='private', required=True)
    is_default = fields.Boolean()
    is_favorite = fields.Boolean()
    layout_config = fields.Json(default=dict)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------
    def _user_is_manager(self):
        return self.env.su or self.env.user.has_group(MANAGER_GROUP)

    def _get_user_access_level(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if self.env.su or user.has_group(MANAGER_GROUP):
            return 'admin'
        if self.user_id == user:
            return 'admin'
        level = None
        for entry in self.access_ids:
            if entry.user_id == user or (
                    entry.group_id and entry.group_id in user.all_group_ids):
                if level is None or (
                        ACCESS_LEVEL_ORDER[entry.access_level]
                        > ACCESS_LEVEL_ORDER[level]):
                    level = entry.access_level
        return level

    def _check_access_level(self, level):
        self.ensure_one()
        current = self._get_user_access_level()
        if not current or ACCESS_LEVEL_ORDER[current] < ACCESS_LEVEL_ORDER[level]:
            raise AccessError(
                _("You are not allowed to access the dashboard '%s'.", self.name))

    def _check_editable(self, level='editor'):
        self.ensure_one()
        self._check_access_level(level)
        if self.dashboard_type == 'predefined' and not self._user_is_manager():
            raise AccessError(_(
                "Predefined dashboards are read-only. Duplicate this dashboard "
                "to customize it."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            owner_id = vals.get('user_id') or self.env.uid
            if owner_id != self.env.uid and not self.env.su \
                    and not self.env.user.has_group(MANAGER_GROUP):
                raise AccessError(
                    _("You can only create dashboards for yourself."))
            if vals.get('dashboard_type') == 'predefined' and not self.env.su \
                    and not self.env.user.has_group(MANAGER_GROUP):
                raise AccessError(
                    _("Only dashboard administrators can create predefined dashboards."))
            vals.setdefault('user_id', self.env.uid)
        return super().create(vals_list)

    def write(self, vals):
        if vals and set(vals) <= {'is_favorite'}:
            for dashboard in self:
                dashboard._check_access_level('viewer')
        else:
            level = 'admin' if ADMIN_ONLY_FIELDS & set(vals) else 'editor'
            for dashboard in self:
                dashboard._check_editable(level)
        return super().write(vals)

    def unlink(self):
        for dashboard in self:
            dashboard._check_editable('admin')
        return super().unlink()

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        for dashboard, vals in zip(self, vals_list):
            vals.update({
                'name': _('%s (copy)', dashboard.name),
                'user_id': self.env.uid,
                'visibility': 'private',
                'dashboard_type': 'dynamic',
                'is_default': False,
                'is_favorite': False,
                'access_ids': [(5, 0, 0)],
            })
        return vals_list

    def action_duplicate(self):
        self.ensure_one()
        self._check_access_level('viewer')
        new_dashboard = self.copy()
        return {
            'type': 'ir.actions.act_window',
            'name': new_dashboard.name,
            'res_model': 'dashboard.suite',
            'res_id': new_dashboard.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_set_default(self):
        self.ensure_one()
        self._check_access_level('viewer')
        if self.user_id != self.env.user and not self._user_is_manager():
            raise AccessError(
                _("Only the owner can set a dashboard as default."))
        self.search([
            ('user_id', '=', self.env.uid),
            ('is_default', '=', True),
        ]).write({'is_default': False})
        self.write({'is_default': True})
        return True

    def action_toggle_favorite(self):
        self.ensure_one()
        self._check_access_level('viewer')
        self.write({'is_favorite': not self.is_favorite})
        return True

    # ------------------------------------------------------------------
    # Data services (RPC)
    # ------------------------------------------------------------------
    def _check_runtime_scope(self):
        self.ensure_one()
        self._check_access_level('viewer')
        if self.company_ids and self.env.company not in self.company_ids:
            raise AccessError(_(
                'This dashboard is not available for your company.'))

    @api.model
    def _normalize_filters(self, filters):
        provided = {}
        for key, value in (filters or {}).items():
            try:
                provided[int(key)] = value
            except (TypeError, ValueError):
                continue
        return provided

    @api.model
    def _filter_default_value(self, dashboard_filter):
        value = dashboard_filter.default_value
        if isinstance(value, dict):
            if 'value' in value:
                return value['value']
        return value

    def _filters_domain(self, model, provided):
        leaves = []
        for dashboard_filter in self.filter_ids:
            field = dashboard_filter.field_id
            if not field or field.model_id.model != model._name:
                continue
            if field.name not in model._fields:
                continue
            value = provided.get(
                dashboard_filter.id,
                self._filter_default_value(dashboard_filter))
            if isinstance(value, dict) and ('from' in value or 'to' in value):
                if value.get('from'):
                    leaves.append([field.name, '>=', value['from']])
                if value.get('to'):
                    leaves.append([field.name, '<=', value['to']])
                continue
            if value is None or value is False or value == '' or value == [] \
                    or value == {}:
                if dashboard_filter.is_required:
                    raise UserError(_(
                        'The filter "%s" is required.', dashboard_filter.name))
                continue
            if field.ttype == 'many2one':
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    continue
            leaves.append([field.name, dashboard_filter.operator, value])
        return leaves

    def _filter_payload(self, dashboard_filter, provided):
        field = dashboard_filter.sudo().field_id
        value = provided.get(
            dashboard_filter.id,
            self._filter_default_value(dashboard_filter))
        return {
            'id': dashboard_filter.id,
            'name': dashboard_filter.name,
            'filter_type': dashboard_filter.filter_type,
            'operator': dashboard_filter.operator,
            'field': field.name if field else None,
            'field_label': field.field_description if field else None,
            'model': field.model_id.model if field else None,
            'default_value': value,
            'is_required': dashboard_filter.is_required,
            'sequence': dashboard_filter.sequence,
        }

    def _widgets_payload(self, provided, offset=0, limit=None, search=None):
        engine = WidgetDataEngine(self.env)
        payloads = []
        for widget in self.widget_ids.sorted(key=lambda w: (w.sequence, w.id)):
            payload = {
                'id': widget.id,
                'name': widget.name,
                'widget_type': widget.widget_type,
                'chart_type': widget.chart_type,
                'position_x': widget.position_x,
                'position_y': widget.position_y,
                'width': widget.width,
                'height': widget.height,
                'sequence': widget.sequence,
            }
            try:
                model = self.env[widget.sudo().model_id.model]
                domain = self._filters_domain(model, provided)
                payload = engine.widget_payload(
                    widget, domain, offset=offset, limit=limit, search=search)
            except (UserError, AccessError, KeyError) as error:
                _logger.warning(
                    'Dashboard %s: widget %s failed: %s',
                    self.id, widget.id, error)
                payload['error'] = str(error)
            payloads.append(payload)
        return payloads

    def _dashboard_payload(self, provided):
        level = self._get_user_access_level()
        can_edit = bool(level) and ACCESS_LEVEL_ORDER[level] >= 2 and (
            self.dashboard_type == 'dynamic' or self._user_is_manager())
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'dashboard_type': self.dashboard_type,
            'visibility': self.visibility,
            'is_favorite': self.is_favorite,
            'is_default': self.is_default,
            'layout_config': self.layout_config or {},
            'access_level': level,
            'can_edit': can_edit,
            'widgets': self._widgets_payload(provided),
            'filters': [
                self._filter_payload(dashboard_filter, provided)
                for dashboard_filter in self.filter_ids.sorted(
                    key=lambda f: (f.sequence, f.id))
            ],
        }

    def get_dashboard_data(self, filters=None):
        """Return the dashboard structure and the data of every widget."""
        self.ensure_one()
        self._check_runtime_scope()
        return self._dashboard_payload(self._normalize_filters(filters))

    def get_widget_data(self, widget_id, offset=0, limit=None, search=None,
                        filters=None):
        """Return the data of one widget, optionally paginating a table."""
        self.ensure_one()
        self._check_runtime_scope()
        widget = self.env['dashboard.suite.widget'].browse(
            int(widget_id)).exists()
        if not widget or widget.dashboard_id.id != self.id:
            raise AccessError(_(
                'This widget does not belong to the dashboard.'))
        provided = self._normalize_filters(filters)
        model = self.env[widget.sudo().model_id.model]
        domain = self._filters_domain(model, provided)
        return WidgetDataEngine(self.env).widget_payload(
            widget, domain, offset=offset, limit=limit, search=search)

    def export_widget_data(self, widget_id, filters=None, search=None):
        """Return a CSV export of a table or chart widget.

        The export is built from the same secured payload as the widget, so
        record rules, field selections and filters are applied identically.
        Rows are capped at ``MAX_GROUPS``.
        """
        self.ensure_one()
        self._check_runtime_scope()
        widget = self.env['dashboard.suite.widget'].browse(
            int(widget_id)).exists()
        if not widget or widget.dashboard_id.id != self.id:
            raise AccessError(_(
                'This widget does not belong to the dashboard.'))
        if widget.widget_type not in ('table', 'chart'):
            raise UserError(_(
                'Only table and chart widgets can be exported.'))
        payload = self.get_widget_data(
            widget_id, 0, MAX_GROUPS, search=search, filters=filters)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        if widget.widget_type == 'table':
            columns = payload['columns']
            writer.writerow([column['label'] for column in columns])
            for row in payload['rows']:
                writer.writerow([
                    self._csv_cell(row['values'].get(column['name']))
                    for column in columns
                ])
        else:
            group_label = (payload.get('group_by') or {}).get('label') \
                or _('Group')
            measure_label = (payload.get('measure') or {}).get('label') \
                or _('Value')
            writer.writerow([group_label, measure_label])
            for row in payload['rows']:
                writer.writerow([row['label'], row['value']])
        content = buffer.getvalue().encode('utf-8-sig')
        return {
            'filename': '%s-%s.csv' % (
                self._export_slug(widget.name), fields.Date.today()),
            'mimetype': 'text/csv',
            'content': base64.b64encode(content).decode('ascii'),
        }

    @staticmethod
    def _csv_cell(value):
        if value is None:
            return ''
        if isinstance(value, bool):
            return _('Yes') if value else _('No')
        return value

    @staticmethod
    def _export_slug(name):
        slug = ''.join(
            character if character.isalnum() else '-'
            for character in (name or '')).strip('-')
        return slug or 'widget'

    def get_filter_options(self, filter_id, limit=80):
        """Return the selectable values of a dashboard filter."""
        self.ensure_one()
        self._check_runtime_scope()
        dashboard_filter = self.filter_ids.filtered(
            lambda f: f.id == int(filter_id))[:1]
        if not dashboard_filter:
            raise UserError(_('The filter does not belong to this dashboard.'))
        field = dashboard_filter.sudo().field_id
        if not field:
            return {'type': 'none', 'options': []}
        model = self.env[field.model_id.model]
        if field.ttype == 'selection':
            selection = model._fields[field.name]._description_selection(
                self.env)
            return {
                'type': 'selection',
                'options': [
                    {'value': value, 'label': label}
                    for value, label in selection
                ],
            }
        if field.ttype == 'many2one':
            comodel = self.env[field.relation]
            page_limit = max(1, min(int(limit or 80), 200))
            records = comodel.search([], limit=page_limit)
            return {
                'type': 'many2one',
                'options': [{
                    'value': record.id,
                    'label': record.sudo().display_name,
                } for record in records],
            }
        return {'type': field.ttype, 'options': []}

    @api.model
    def _find_default_dashboard(self):
        dashboard = self.browse()
        for candidate in self.search(
                [('active', '=', True)],
                order='is_default desc, is_favorite desc, sequence, id'):
            if not candidate._get_user_access_level():
                continue
            if candidate.company_ids and self.env.company not in candidate.company_ids:
                continue
            dashboard = candidate
            break
        return dashboard

    @api.model
    def get_default_dashboard_data(self, filters=None):
        """Return the data of the user's default dashboard.

        Used by the generic client action when no dashboard is selected.
        """
        dashboard = self._find_default_dashboard()
        if not dashboard:
            raise UserError(_(
                'No dashboard is available for this user. Create one or ask '
                'an administrator to share a dashboard with you.'))
        return dashboard.get_dashboard_data(filters)

    def action_open(self):
        """Open this dashboard in the OWL client action."""
        self.ensure_one()
        self._check_runtime_scope()
        return {
            'type': 'ir.actions.client',
            'name': self.name,
            'tag': 'dashboard_suite_core.dashboard_action',
            'params': {'dashboard_id': self.id},
            'target': 'current',
        }

    def save_layout(self, layout):
        """Persist the widget order and sizes edited from the client action."""
        self.ensure_one()
        self._check_runtime_scope()
        self._check_editable('editor')
        if not isinstance(layout, list):
            raise UserError(_('Invalid layout payload.'))
        widgets = self.widget_ids
        allowed = set(widgets.ids)
        seen = set()
        entries = []
        for entry in layout:
            if not isinstance(entry, dict):
                raise UserError(_('Invalid layout payload.'))
            try:
                widget_id = int(entry.get('id'))
            except (TypeError, ValueError):
                raise UserError(_('Invalid widget in the layout payload.'))
            if widget_id not in allowed:
                raise AccessError(_(
                    'This widget does not belong to the dashboard.'))
            if widget_id in seen:
                raise UserError(_('Duplicate widget in the layout payload.'))
            seen.add(widget_id)
            entries.append((widget_id, entry))
        for widget_id, entry in entries:
            vals = {}
            for key, maximum in (
                    ('width', GRID_COLUMNS), ('height', MAX_GRID_HEIGHT)):
                if key not in entry:
                    continue
                try:
                    value = int(entry[key])
                except (TypeError, ValueError):
                    raise UserError(_(
                        'Invalid %s in the layout payload.', key))
                vals[key] = max(1, min(value, maximum))
            if 'sequence' in entry:
                try:
                    vals['sequence'] = max(0, int(entry['sequence']))
                except (TypeError, ValueError):
                    raise UserError(_(
                        'Invalid sequence in the layout payload.'))
            if vals:
                widgets.browse(widget_id).write(vals)
        return True
