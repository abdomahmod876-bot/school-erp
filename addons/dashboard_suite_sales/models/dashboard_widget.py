from datetime import timedelta

from odoo import _, models
from odoo.exceptions import ValidationError

from .sales_target import METRICS


class DashboardSuiteWidget(models.Model):
    _inherit = 'dashboard.suite.widget'

    def _sales_target_config(self):
        self.ensure_one()
        return self.config if isinstance(self.config, dict) else {}

    def _sales_target_record(self):
        self.ensure_one()
        if self._sales_target_config().get('target_source') != 'sales_target':
            return self.env['dashboard.suite.sales.target']
        return self.env['dashboard.suite.sales.target']._find_target()

    def _sales_target_metric(self):
        metric = self._sales_target_config().get('target_metric') or 'amount'
        if metric not in METRICS:
            raise ValidationError(_(
                'Unsupported sales target metric "%(metric)s" in widget '
                '"%(widget)s".', metric=metric, widget=self.name))
        return metric

    def _sales_target_date_field(self):
        config = self._sales_target_config()
        date_field = self.sudo().date_field_id.name
        field_name = config.get('target_date_field') or date_field \
            or 'date_order'
        model_name = self.sudo().model_id.model
        field = (self.env[model_name]._fields.get(field_name)
                 if model_name in self.env else None)
        if not field or field.type not in ('date', 'datetime'):
            raise ValidationError(_(
                'Widget "%(widget)s" needs a valid date field for its sales '
                'target (got "%(field)s").',
                widget=self.name, field=field_name))
        return field_name

    def _uses_dynamic_target(self):
        return self._sales_target_config().get('target_source') \
            == 'sales_target'

    def _validate_config(self, model_name):
        super()._validate_config(model_name)
        source = self._sales_target_config().get('target_source')
        if not source:
            return
        if source != 'sales_target':
            raise ValidationError(_(
                'Unsupported target source "%s".', source))
        self._sales_target_metric()
        self._sales_target_date_field()

    def _resolve_dashboard_target(self):
        self.ensure_one()
        target = self._sales_target_record()
        if not target:
            return None
        return target._metric_value(self._sales_target_metric())

    def _resolve_dashboard_domain(self):
        self.ensure_one()
        target = self._sales_target_record()
        if not target:
            return []
        field_name = self._sales_target_date_field()
        return [
            (field_name, '>=', target.date_start),
            (field_name, '<', target.date_end + timedelta(days=1)),
        ]
