"""Aggregation engine for dashboard widgets.

Runs ``_read_group`` queries through the user's environment so that record
rules, field access rights and multi-company rules are enforced by the ORM.
Monetary measures are converted to the current company currency with
``res.currency._convert``; no caching in the MVP.
"""

from datetime import date, datetime

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from .domain_validator import validate_domain

GRANULARITIES = ('day', 'week', 'month', 'quarter', 'year')
MAX_GROUPS = 500
MEASURE_TYPES = ('integer', 'float', 'monetary')
TEMPORAL_TYPES = ('date', 'datetime')


class AggregationEngine:
    """Safely aggregate one widget over a model."""

    def __init__(self, env, widget):
        self.env = env
        self.widget = widget
        metadata = widget.sudo()
        model_ref = metadata.model_id
        model_name = model_ref.model if model_ref else None
        if not model_name or model_name not in env:
            raise ValidationError(_(
                'The data model of widget "%s" is not available.', widget.name))
        self.model = env[model_name]
        if self.model._transient or self.model._abstract:
            raise ValidationError(_(
                'Widget "%s" cannot use model "%s".', widget.name, model_name))
        self.measure = metadata.measure_field_id or None
        self.group_by = metadata.group_by_field_id or None
        self.date_field = metadata.date_field_id or None
        for field, label in (
                (self.measure, _('measure field')),
                (self.group_by, _('group by field')),
                (self.date_field, _('date field'))):
            if not field:
                continue
            if field.model_id.model != model_name:
                raise ValidationError(_(
                    'The %(label)s of widget "%(widget)s" does not belong to '
                    'model "%(model)s".',
                    label=label, widget=widget.name, model=model_name))
            if field.name not in self.model._fields:
                raise ValidationError(_(
                    'The field "%(field)s" of widget "%(widget)s" no longer '
                    'exists on model "%(model)s".',
                    field=field.name, widget=widget.name, model=model_name))
        self.config = widget.config or {}
        if not isinstance(self.config, dict):
            raise ValidationError(_(
                'The configuration of widget "%s" must be an object.',
                widget.name))

    # ------------------------------------------------------------------
    # Specs
    # ------------------------------------------------------------------
    def _aggregate_spec(self):
        operation = self.widget.operation
        if operation == 'count':
            return '__count', 'count'
        if not self.measure:
            raise ValidationError(_(
                'Widget "%s" needs a measure field.', self.widget.name))
        field = self.model._fields[self.measure.name]
        if field.type not in MEASURE_TYPES:
            raise ValidationError(_(
                'The field "%(field)s" of widget "%(widget)s" is not numeric.',
                field=field.string, widget=self.widget.name))
        return f'{field.name}:{operation}', operation

    def _granularity(self):
        value = self.config.get('granularity') or 'month'
        if value not in GRANULARITIES:
            raise ValidationError(_(
                'Unsupported date granularity "%s" in widget "%s".',
                value, self.widget.name))
        return value

    def _groupby_specs(self, grouped):
        if not grouped:
            return []
        if self.group_by:
            field_name = self.group_by.name
            if self.model._fields[field_name].type in TEMPORAL_TYPES:
                return [f'{field_name}:{self._granularity()}']
            return [field_name]
        if self.date_field:
            return [f'{self.date_field.name}:{self._granularity()}']
        return []

    def _currency_field_name(self):
        if not self.measure:
            return None
        field = self.model._fields[self.measure.name]
        if field.type != 'monetary':
            return None
        currency_name = field.get_currency_field(self.model)
        if currency_name and currency_name in self.model._fields \
                and self.model._fields[currency_name].store:
            return currency_name
        return None

    def _currency_payload(self):
        currency = self.env.company.currency_id
        return {
            'id': currency.id,
            'name': currency.name,
            'symbol': currency.symbol,
            'position': currency.position,
            'decimal_places': currency.decimal_places,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def compute(self, domain, grouped=False, offset=0, limit=None):
        validate_domain(self.model, domain, _('widget domain'))
        aggregate_spec, operation = self._aggregate_spec()
        specs = self._groupby_specs(grouped)
        if grouped and not specs:
            raise ValidationError(_(
                'Widget "%s" needs a group by field or a date field.',
                self.widget.name))
        currency_name = self._currency_field_name()
        read_specs = list(specs)
        read_fields = {spec.split(':')[0] for spec in read_specs}
        if currency_name and currency_name not in read_fields:
            read_specs.append(currency_name)
        total = self._total(domain, aggregate_spec, currency_name)
        rows = []
        has_more = False
        if grouped:
            raw_rows = self.model._read_group(
                domain, groupby=read_specs, aggregates=[aggregate_spec],
                limit=MAX_GROUPS)
            merged = self._merge_rows(raw_rows, specs, read_specs, currency_name)
            self._sort_rows(merged, specs)
            page_offset = max(0, int(offset or 0))
            page_limit = limit if limit is not None else (self.widget.limit or 10)
            page_limit = max(1, min(int(page_limit), MAX_GROUPS))
            has_more = len(merged) > page_offset + page_limit
            rows = merged[page_offset:page_offset + page_limit]
        return {
            'rows': rows,
            'total': total,
            'has_more': has_more,
            'operation': operation,
            'measure': self._measure_payload(operation),
            'group_by': self._group_payload(specs),
            'currency': self._currency_payload() if currency_name else None,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _measure_payload(self, operation):
        if operation == 'count' or not self.measure:
            return {
                'field': None,
                'label': _('Count'),
                'operation': 'count',
                'type': 'integer',
            }
        return {
            'field': self.measure.name,
            'label': self.measure.field_description,
            'operation': operation,
            'type': self.model._fields[self.measure.name].type,
        }

    def _group_payload(self, specs):
        if not specs:
            return None
        spec = specs[0]
        field_name = spec.split(':')[0]
        field = self.model._fields[field_name]
        return {
            'field': field_name,
            'label': field.string,
            'type': field.type,
            'granularity': spec.split(':')[1] if ':' in spec else None,
        }

    def _total(self, domain, aggregate_spec, currency_name):
        if not currency_name:
            result = self.model._read_group(domain, aggregates=[aggregate_spec])
            value = result[0][0] if result else 0
            return self._clean_number(value)
        rows = self.model._read_group(
            domain, groupby=[currency_name], aggregates=[aggregate_spec],
            limit=MAX_GROUPS)
        today = fields.Date.context_today(self.model)
        total = 0.0
        for currency_value, amount in rows:
            total += self._convert(amount, currency_value, today)
        return total

    def _merge_rows(self, raw_rows, specs, read_specs, currency_name):
        currency_index = None
        if currency_name:
            for index, spec in enumerate(read_specs):
                if spec.split(':')[0] == currency_name:
                    currency_index = index
                    break
        merged = {}
        for row in raw_rows:
            values = list(row[:len(read_specs)])
            amount = row[len(read_specs)] if len(row) > len(read_specs) else 0
            if currency_index is not None:
                amount = self._convert(
                    amount, values[currency_index], self._row_date(read_specs, values))
            user_values = values[:len(specs)]
            key, label = self._key_label(specs, user_values)
            entry = merged.get(key)
            if entry:
                entry['value'] += self._clean_number(amount)
            else:
                merged[key] = {
                    'key': key,
                    'label': label,
                    'value': self._clean_number(amount),
                }
        return list(merged.values())

    def _key_label(self, specs, values):
        if not specs:
            return False, ''
        if len(specs) == 1:
            return self._value_key_label(specs[0], values[0])
        keys, labels = [], []
        for spec, value in zip(specs, values):
            key, label = self._value_key_label(spec, value)
            keys.append(key)
            labels.append(label)
        return tuple(keys), ' / '.join(label for label in labels if label)

    def _value_key_label(self, spec, value):
        field_name = spec.split(':')[0]
        field = self.model._fields[field_name]
        if field.type == 'many2one':
            if not value:
                return False, ''
            return value.id, value.sudo().display_name or ''
        if field.type == 'selection':
            label = dict(field._description_selection(self.env)).get(value)
            return value, label or ''
        if field.type in TEMPORAL_TYPES:
            label = self._format_date(value, spec.split(':')[1] if ':' in spec else None)
            return label, label
        if field.type == 'boolean':
            return bool(value), _('Yes') if value else _('No')
        if value is None or value is False:
            return False, ''
        return value, str(value)

    def _row_date(self, specs, values):
        for spec, value in zip(specs, values):
            field_name = spec.split(':')[0]
            if self.model._fields[field_name].type not in TEMPORAL_TYPES or not value:
                continue
            return self._to_date(value)
        return None

    @staticmethod
    def _to_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                if len(value) > 10:
                    return fields.Datetime.to_datetime(value).date()
                return fields.Date.to_date(value)
            except (ValueError, TypeError):
                return None
        return None

    def _format_date(self, value, granularity):
        value = self._to_date(value)
        if not value:
            return ''
        granularity = granularity or 'month'
        if granularity == 'day':
            return value.isoformat()
        if granularity == 'week':
            year, week, _weekday = value.isocalendar()
            return f'{year}-W{week:02d}'
        if granularity == 'month':
            return f'{value.year:04d}-{value.month:02d}'
        if granularity == 'quarter':
            return f'{value.year:04d}-Q{(value.month - 1) // 3 + 1}'
        return f'{value.year:04d}'

    def _convert(self, amount, currency_value, date_value=None):
        if amount is None or amount is False:
            return 0.0
        if isinstance(currency_value, models.BaseModel):
            currency = currency_value
        elif currency_value:
            currency = self.env['res.currency'].browse(currency_value)
        else:
            currency = self.env['res.currency']
        display = self.env.company.currency_id
        if not currency or currency == display:
            return float(amount)
        return currency._convert(
            float(amount), display, self.env.company,
            date_value or fields.Date.context_today(self.model))

    @staticmethod
    def _clean_number(value):
        if value is None or value is False:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return float(value)

    def _sort_rows(self, rows, specs):
        if specs and self.model._fields[specs[0].split(':')[0]].type in TEMPORAL_TYPES:
            rows.sort(key=lambda row: str(row['key']))
        else:
            rows.sort(key=lambda row: (-(row['value'] or 0), str(row['label'])))
