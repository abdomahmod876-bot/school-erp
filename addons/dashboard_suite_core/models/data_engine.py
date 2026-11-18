"""Builds the JSON payload consumed by the dashboard frontend."""

from odoo import _, fields
from odoo.exceptions import ValidationError

from .aggregation_engine import MAX_GROUPS, AggregationEngine
from .domain_validator import combine_domains, validate_domain


def format_number(value, decimal_places=None):
    if value is None or value is False:
        value = 0
    if isinstance(value, bool):
        return str(int(value))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimal_places is None:
        decimal_places = 0 if number.is_integer() else 2
    return f'{number:,.{decimal_places}f}'


class WidgetDataEngine:
    """Resolve a widget configuration into displayable data."""

    def __init__(self, env):
        self.env = env

    def widget_payload(self, widget, extra_domain=None, offset=0, limit=None,
                       search=None):
        domain = combine_domains(widget.domain or [], extra_domain or [])
        domain = combine_domains(
            domain, widget._resolve_dashboard_domain() or [])
        base = {
            'id': widget.id,
            'name': widget.name,
            'widget_type': widget.widget_type,
            'model': widget.sudo().model_id.model,
            'chart_type': widget.chart_type,
            'position_x': widget.position_x,
            'position_y': widget.position_y,
            'width': widget.width,
            'height': widget.height,
            'sequence': widget.sequence,
            'config': widget.config or {},
        }
        if widget.widget_type == 'table':
            base.update(self._table_payload(
                widget, domain, offset=offset, limit=limit, search=search))
            base['measure'] = None
            return base
        engine = AggregationEngine(self.env, widget)
        result = engine.compute(
            domain, grouped=widget.widget_type == 'chart',
            offset=offset, limit=limit)
        base['measure'] = result['measure']
        base['currency'] = result['currency']
        if widget.widget_type == 'kpi':
            base['value'] = result['total']
            base['formatted_value'] = format_number(
                result['total'],
                result['currency']['decimal_places'] if result['currency'] else None)
            base['target'], base['progress'] = self._target_progress(
                widget, result['total'])
        elif widget.widget_type == 'chart':
            base['chart_type'] = widget.chart_type
            base['group_by'] = result['group_by']
            base['labels'] = [row['label'] for row in result['rows']]
            base['datasets'] = [{
                'label': result['measure']['label'],
                'data': [row['value'] for row in result['rows']],
            }]
            base['rows'] = result['rows']
            base['total'] = result['total']
            base['has_more'] = result['has_more']
        else:
            base['value'] = result['total']
            base['formatted_value'] = format_number(
                result['total'],
                result['currency']['decimal_places'] if result['currency'] else None)
            base['target'], base['progress'] = self._target_progress(
                widget, result['total'])
            base['remaining'] = (
                max(base['target'] - result['total'], 0)
                if base['target'] else None)
        return base

    # ------------------------------------------------------------------
    # KPI helpers
    # ------------------------------------------------------------------
    def _target_progress(self, widget, value):
        config = widget.config if isinstance(widget.config, dict) else {}
        target = widget._resolve_dashboard_target()
        if target is None:
            target = config.get('target')
        if target is None:
            return None, None
        try:
            target = float(target)
        except (TypeError, ValueError):
            return None, None
        if target <= 0:
            return target, None
        return target, round((value or 0) / target * 100, 1)

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------
    def _table_payload(self, widget, domain, offset=0, limit=None, search=None):
        metadata = widget.sudo()
        model_ref = metadata.model_id
        if not model_ref or model_ref.model not in self.env:
            raise ValidationError(_(
                'The data model of widget "%s" is not available.', widget.name))
        model = self.env[model_ref.model]
        if model._transient or model._abstract:
            raise ValidationError(_(
                'Widget "%s" cannot use model "%s".', widget.name, model._name))
        if search:
            domain = combine_domains(
                domain, [('display_name', 'ilike', search.strip())])
        validate_domain(model, domain, _('table filter'))
        config = widget.config if isinstance(widget.config, dict) else {}
        columns = config.get('columns') or ['display_name']
        for column in columns:
            if not isinstance(column, str) or column not in model._fields:
                raise ValidationError(_(
                    'Unknown column "%s" in widget "%s".', column, widget.name))
        direction = config.get('sort_direction') or 'desc'
        if direction not in ('asc', 'desc'):
            direction = 'desc'
        order = None
        if metadata.sort_field_id:
            order = f'{metadata.sort_field_id.name} {direction}'
        page_limit = max(1, min(int(limit or widget.limit or 10), MAX_GROUPS))
        page_offset = max(0, int(offset or 0))
        records = model.search(
            domain, offset=page_offset, limit=page_limit, order=order)
        total = model.search_count(domain)
        rows = []
        for record in records:
            rows.append({
                'id': record.id,
                'values': {
                    column: self._format_record_value(record, column)
                    for column in columns
                },
            })
        return {
            'columns': [{
                'name': column,
                'label': model._fields[column].string,
                'type': model._fields[column].type,
            } for column in columns],
            'rows': rows,
            'total': total,
            'offset': page_offset,
            'limit': page_limit,
            'has_more': total > page_offset + len(rows),
        }

    def _format_record_value(self, record, field_name):
        field = record._fields[field_name]
        value = record[field_name]
        if field.type == 'many2one':
            return value.sudo().display_name if value else ''
        if field.type in ('one2many', 'many2many'):
            return ', '.join(value.sudo().mapped('display_name'))
        if field.type == 'selection':
            label = dict(field._description_selection(self.env)).get(value)
            return label or ''
        if field.type == 'monetary':
            currency = None
            currency_name = field.get_currency_field(record)
            if currency_name and currency_name in record._fields:
                currency = record[currency_name]
            return format_number(
                value, currency.decimal_places if currency else None)
        if field.type == 'datetime':
            return value.isoformat(sep=' ') if value else ''
        if field.type == 'date':
            return fields.Date.to_string(value) if value else ''
        if field.type == 'boolean':
            return bool(value)
        if field.type == 'integer':
            return int(value or 0)
        if field.type == 'float':
            return float(value or 0.0)
        if value is None or value is False:
            return ''
        return value
