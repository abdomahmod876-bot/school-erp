from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .aggregation_engine import GRANULARITIES, MAX_GROUPS
from .domain_validator import validate_domain

NUMERIC_TYPES = ('integer', 'float', 'monetary')
GROUPABLE_TYPES = (
    'many2one', 'selection', 'char', 'boolean', 'integer', 'date', 'datetime',
)
DATE_TYPES = ('date', 'datetime')
UNSORTABLE_TYPES = ('one2many', 'many2many', 'binary', 'json', 'html')
UNREADABLE_COLUMN_TYPES = ('binary', 'html')
MAX_LIMIT = MAX_GROUPS


class DashboardSuiteWidget(models.Model):
    _name = 'dashboard.suite.widget'
    _description = 'Dashboard Widget'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    dashboard_id = fields.Many2one(
        'dashboard.suite', required=True, ondelete='cascade', index=True)
    widget_type = fields.Selection(
        selection=[
            ('kpi', 'KPI'),
            ('chart', 'Chart'),
            ('table', 'Table'),
            ('progress', 'Progress'),
        ],
        default='kpi', required=True)
    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        index=True)
    measure_field_id = fields.Many2one(
        'ir.model.fields', string='Measure Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['integer', 'float', 'monetary'])]")
    group_by_field_id = fields.Many2one(
        'ir.model.fields', string='Group By',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['many2one', 'selection', 'char', 'boolean', "
               "'integer', 'date', 'datetime'])]")
    date_field_id = fields.Many2one(
        'ir.model.fields', string='Date Field',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'in', ['date', 'datetime'])]")
    sort_field_id = fields.Many2one(
        'ir.model.fields', string='Sort Field',
        domain="[('model_id', '=', model_id), ('store', '=', True)]")
    operation = fields.Selection(
        selection=[
            ('count', 'Count'),
            ('sum', 'Sum'),
            ('avg', 'Average'),
            ('min', 'Minimum'),
            ('max', 'Maximum'),
        ],
        default='count', required=True)
    chart_type = fields.Selection(
        selection=[
            ('bar', 'Bar'),
            ('line', 'Line'),
            ('pie', 'Pie'),
            ('doughnut', 'Doughnut'),
            ('area', 'Area'),
        ],
        default='bar')
    domain = fields.Json(
        default=list,
        help='Structured domain: a JSON list of [field, operator, value] '
             'items or logical operators "&", "|" and "!" (prefix notation). '
             'Example: [["state", "=", "sale"]].')
    config = fields.Json(
        default=dict,
        help='Widget presentation settings (colors, columns, targets, ...).')
    position_x = fields.Integer(default=0)
    position_y = fields.Integer(default=0)
    width = fields.Integer(default=4, help='Width in grid columns (1-12).')
    height = fields.Integer(default=2, help='Height in grid rows.')
    limit = fields.Integer(default=10)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Extension points
    # ------------------------------------------------------------------
    def _resolve_dashboard_domain(self):
        """Extra domain leaves for modules with dynamic widget scopes."""
        return []

    def _resolve_dashboard_target(self):
        """Dynamic numeric target, or None to fall back on config['target']."""
        return None

    def _uses_dynamic_target(self):
        """Whether a progress widget gets its target from an extension."""
        return False

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
        for widget in self:
            widget.dashboard_id._check_editable('editor')
        return super().write(vals)

    def unlink(self):
        for widget in self:
            widget.dashboard_id._check_editable('editor')
        return super().unlink()

    # ------------------------------------------------------------------
    # Configuration validation
    # ------------------------------------------------------------------
    @api.constrains(
        'model_id', 'measure_field_id', 'group_by_field_id', 'date_field_id',
        'sort_field_id', 'operation', 'widget_type', 'chart_type', 'domain',
        'config', 'limit', 'width', 'height')
    def _check_configuration(self):
        for widget in self:
            widget._validate_configuration()

    def _validate_configuration(self):
        self.ensure_one()
        model = self.sudo().model_id
        if not model:
            raise ValidationError(_('Select a model for widget "%s".', self.name))
        model_name = model.model
        measure = self.sudo().measure_field_id
        group_by = self.sudo().group_by_field_id
        date_field = self.sudo().date_field_id
        sort_field = self.sudo().sort_field_id

        if measure:
            self._check_field_type(
                measure, model_name, 'Measure Field', NUMERIC_TYPES, stored=True)
        if self.operation != 'count' and not measure:
            raise ValidationError(_(
                'Widget "%s" uses an aggregation and needs a measure field.',
                self.name))
        if group_by:
            self._check_field_type(
                group_by, model_name, 'Group By', GROUPABLE_TYPES, stored=True)
        if self.widget_type == 'chart':
            if not self.chart_type:
                raise ValidationError(
                    _('Select a chart type for widget "%s".', self.name))
            if not group_by and not date_field:
                raise ValidationError(_(
                    'Select a group by field or a date field for chart '
                    'widget "%s".', self.name))
        if date_field:
            self._check_field_type(
                date_field, model_name, 'Date Field', DATE_TYPES, stored=True)
        if sort_field:
            self._check_field_type(
                sort_field, model_name, 'Sort Field', None, stored=True,
                excluded=UNSORTABLE_TYPES)
        if not 1 <= (self.limit or 0) <= MAX_LIMIT:
            raise ValidationError(_(
                'The limit of widget "%(widget)s" must be between 1 and %(max)s.',
                widget=self.name, max=MAX_LIMIT))
        if not 1 <= (self.width or 0) <= 12:
            raise ValidationError(_(
                'The width of widget "%s" must be between 1 and 12.', self.name))
        if (self.height or 0) < 1:
            raise ValidationError(_(
                'The height of widget "%s" must be at least 1.', self.name))
        self._validate_domain()
        self._validate_config(model_name)

    @api.model
    def _check_field_type(self, field, model_name, label, allowed_types,
                          stored=False, excluded=()):
        if field.model_id.model != model_name:
            raise ValidationError(_(
                'The field "%(field)s" does not belong to model "%(model)s" '
                '(%(label)s).', field=field.name, model=model_name, label=label))
        if stored and not field.store:
            raise ValidationError(_(
                'The field "%(field)s" cannot be used as %(label)s because it '
                'is not stored.', field=field.field_description, label=label))
        if allowed_types and field.ttype not in allowed_types:
            raise ValidationError(_(
                'The field "%(field)s" cannot be used as %(label)s: type '
                '"%(type)s" is not supported.',
                field=field.field_description, label=label, type=field.ttype))
        if field.ttype in excluded:
            raise ValidationError(_(
                'The field "%(field)s" cannot be used as %(label)s.',
                field=field.field_description, label=label))

    def _validate_domain(self):
        self.ensure_one()
        model_ref = self.sudo().model_id
        if not model_ref or model_ref.model not in self.env:
            return
        validate_domain(
            self.env[model_ref.model], self.domain or [],
            _('filter of widget "%s"', self.name))

    def _validate_config(self, model_name):
        self.ensure_one()
        config = self.config or {}
        if not isinstance(config, dict):
            raise ValidationError(_(
                'The configuration of widget "%s" must be an object.', self.name))
        columns = config.get('columns')
        if columns:
            if not isinstance(columns, list):
                raise ValidationError(_(
                    'The list columns of widget "%s" must be a list of fields.',
                    self.name))
            model = self.env[model_name]
            for column in columns:
                if not isinstance(column, str) or column not in model._fields:
                    raise ValidationError(_(
                        'Unknown column "%s" in widget "%s".', column, self.name))
                if model._fields[column].type in UNREADABLE_COLUMN_TYPES:
                    raise ValidationError(_(
                        'The column "%s" cannot be displayed in a table.',
                        column))
        granularity = config.get('granularity')
        if granularity is not None and granularity not in GRANULARITIES:
            raise ValidationError(_(
                'Unsupported date granularity "%s" in widget "%s".',
                granularity, self.name))
        sort_direction = config.get('sort_direction')
        if sort_direction is not None and sort_direction not in ('asc', 'desc'):
            raise ValidationError(_(
                'The sort direction of widget "%s" must be "asc" or "desc".',
                self.name))
        target = config.get('target')
        if target is not None:
            try:
                target_value = float(target)
            except (TypeError, ValueError):
                raise ValidationError(_(
                    'The target of widget "%s" must be a number.', self.name))
            if target_value < 0:
                raise ValidationError(_(
                    'The target of widget "%s" cannot be negative.', self.name))
        if self.widget_type == 'progress' and target is None \
                and not self._uses_dynamic_target():
            raise ValidationError(_(
                'Widget "%s" is a progress widget and requires a target.',
                self.name))
