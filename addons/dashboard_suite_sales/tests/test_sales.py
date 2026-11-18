import calendar
import unittest
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

GROUP_VIEWER = 'dashboard_suite_core.group_dashboard_viewer'
GROUP_EDITOR = 'dashboard_suite_core.group_dashboard_editor'
GROUP_MANAGER = 'dashboard_suite_core.group_dashboard_manager'


def month_bounds(today):
    start = today.replace(day=1)
    end = today.replace(
        day=calendar.monthrange(today.year, today.month)[1])
    return start, end


@tagged('post_install', '-at_install')
class TestSalesTargets(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.target_model = cls.env['dashboard.suite.sales.target']
        cls.today = fields.Date.context_today(cls.target_model)
        cls.month_start, cls.month_end = month_bounds(cls.today)
        cls.viewer = new_test_user(
            cls.env, login='ds_sales_viewer',
            groups='base.group_user,sales_team.group_sale_salesman,' + GROUP_VIEWER,
            company_id=cls.company.id)
        cls.editor = new_test_user(
            cls.env, login='ds_sales_editor',
            groups='base.group_user,' + GROUP_EDITOR,
            company_id=cls.company.id)
        cls.manager = new_test_user(
            cls.env, login='ds_sales_manager',
            groups='base.group_user,' + GROUP_MANAGER,
            company_id=cls.company.id)
        cls.company_target = cls.target_model.create({
            'company_id': cls.company.id,
            'date_start': cls.month_start,
            'date_end': cls.month_end,
            'target_amount': 1000.0,
            'target_orders': 20,
        })

    def _create_target(self, **values):
        defaults = {
            'company_id': self.company.id,
            'date_start': self.month_start,
            'date_end': self.month_end,
            'target_amount': 500.0,
        }
        defaults.update(values)
        return self.target_model.create(defaults)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def test_defaults_and_name(self):
        self.assertEqual(self.month_start.day, 1)
        self.assertEqual(self.company_target.currency_id, self.company.currency_id)
        self.assertIn(self.company.name, self.company_target.name)
        self.assertIn(str(self.month_start), self.company_target.name)

    def test_end_before_start_raises(self):
        with self.assertRaises(ValidationError):
            self._create_target(
                date_start=self.month_end, date_end=self.month_start + timedelta(
                    days=-1))

    def test_overlap_same_scope_raises(self):
        with self.assertRaises(ValidationError):
            self._create_target(target_amount=200.0)

    def test_adjacent_period_allowed(self):
        target = self._create_target(
            date_start=self.month_end + timedelta(days=1),
            date_end=self.month_end + timedelta(days=30))
        self.assertTrue(target)

    def test_different_scope_allowed(self):
        target = self._create_target(user_id=self.viewer.id)
        self.assertEqual(target.user_id, self.viewer)

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------
    def test_editor_cannot_manage_targets(self):
        with self.assertRaises(AccessError):
            self.target_model.with_user(self.editor).create({
                'company_id': self.company.id,
                'date_start': self.month_end + timedelta(days=1),
                'date_end': self.month_end + timedelta(days=30),
            })
        with self.assertRaises(AccessError):
            self.company_target.with_user(self.editor).write(
                {'target_amount': 1.0})
        with self.assertRaises(AccessError):
            self.company_target.with_user(self.editor).unlink()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def test_company_target_resolution(self):
        self.assertEqual(self.target_model._resolve('amount'), 1000.0)
        self.assertEqual(self.target_model._resolve('orders'), 20.0)
        outside = self.month_start - timedelta(days=1)
        self.assertIsNone(
            self.target_model._resolve('amount', date_value=outside))

    def test_user_target_overrides_company_target(self):
        self._create_target(
            user_id=self.viewer.id, target_amount=400.0)
        self.assertEqual(
            self.target_model._resolve(
                'amount', user=self.viewer.with_env(self.env)), 400.0)
        self.assertEqual(self.target_model._resolve('amount'), 1000.0)

    def test_team_target_used_when_no_user_target(self):
        team = self.env['crm.team'].create({'name': 'Dashboard Sales Team'})
        team.member_ids = [(4, self.viewer.id)]
        self._create_target(team_id=team.id, target_amount=700.0)
        self.assertEqual(team.member_ids, self.viewer)
        self.assertEqual(
            self.target_model._resolve(
                'amount', user=self.viewer.with_env(self.env)), 700.0)

    def test_orders_metric_missing_returns_none(self):
        self._create_target(user_id=self.viewer.id)
        self.assertIsNone(self.target_model._resolve(
            'orders', user=self.viewer.with_env(self.env)))


@tagged('post_install', '-at_install')
class TestSalesDashboards(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'sale.order' not in cls.env:
            raise unittest.SkipTest('sale is required for the sales dashboards')
        cls.company = cls.env.company
        cls.today = fields.Date.context_today(cls.env['sale.order'])
        cls.month_start, cls.month_end = month_bounds(cls.today)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Dashboard Sales Partner',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Dashboard Sales Product',
            'list_price': 100.0,
            'taxes_id': [(5, 0, 0)],
        })
        cls.quotation = cls._make_order(100.0)
        cls.sale_1 = cls._make_order(200.0, confirm=True)
        cls.sale_2 = cls._make_order(400.0, confirm=True)
        cls.old_sale = cls._make_order(50.0, confirm=True)
        cls.old_sale.write({
            'date_order': cls.today - timedelta(days=60),
        })
        cls.dashboard = cls.env.ref(
            'dashboard_suite_sales.dashboard_sales_overview')
        cls.target = cls.env['dashboard.suite.sales.target'].create({
            'company_id': cls.company.id,
            'date_start': cls.month_start,
            'date_end': cls.month_end,
            'target_amount': 1000.0,
            'target_orders': 20,
        })
        cls.viewer = new_test_user(
            cls.env, login='ds_sales_dash_viewer',
            groups='base.group_user,sales_team.group_sale_salesman,' + GROUP_VIEWER,
            company_id=cls.company.id)

    @classmethod
    def _make_order(cls, price, confirm=False):
        vals = {
            'partner_id': cls.partner.id,
            'user_id': cls.env.uid,
            'date_order': cls.today,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1.0,
                'price_unit': price,
                'tax_ids': [(5, 0, 0)],
            })],
        }
        order = cls.env['sale.order'].create(vals)
        if confirm:
            order.action_confirm()
        return order

    def _widget_payloads(self, dashboard=None, filters=None):
        dashboard = dashboard or self.dashboard
        payload = dashboard.get_dashboard_data(filters=filters)
        return payload, {
            widget['id']: widget for widget in payload['widgets']
        }

    def _widget_id(self, xmlid):
        return self.env.ref('dashboard_suite_sales.' + xmlid).id

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def test_predefined_dashboard_loaded(self):
        self.assertEqual(self.dashboard.dashboard_type, 'predefined')
        self.assertEqual(self.dashboard.visibility, 'shared')
        self.assertEqual(len(self.dashboard.widget_ids), 8)
        self.assertEqual(len(self.dashboard.filter_ids), 2)
        self.assertEqual(
            self.dashboard.access_ids.group_id,
            self.env.ref(GROUP_VIEWER))

    def test_viewer_payload_has_no_widget_errors(self):
        payload = self.dashboard.with_user(self.viewer).get_dashboard_data()
        self.assertEqual(payload['access_level'], 'viewer')
        self.assertFalse(payload['can_edit'])
        for widget in payload['widgets']:
            self.assertNotIn('error', widget, widget['name'])

    # ------------------------------------------------------------------
    # Values
    # ------------------------------------------------------------------
    def test_kpi_values(self):
        confirmed = self.env['sale.order'].search([
            ('state', 'in', ['sale'])])
        payload, widgets = self._widget_payloads()
        amount_widget = widgets[self._widget_id('widget_sales_confirmed_amount')]
        orders_widget = widgets[self._widget_id('widget_sales_confirmed_orders')]
        average_widget = widgets[self._widget_id('widget_sales_average_order')]
        self.assertAlmostEqual(
            amount_widget['value'], sum(confirmed.mapped('amount_untaxed')),
            places=2)
        self.assertEqual(orders_widget['value'], len(confirmed))
        self.assertAlmostEqual(
            average_widget['value'],
            sum(confirmed.mapped('amount_untaxed')) / len(confirmed), places=2)
        self.assertEqual(amount_widget['currency']['id'],
                         self.company.currency_id.id)

    def test_progress_widget_uses_sales_target_and_period(self):
        payload, widgets = self._widget_payloads()
        progress = widgets[self._widget_id('widget_sales_month_target')]
        expected = sum(self.env['sale.order'].search([
            ('state', 'in', ['sale']),
            ('date_order', '>=', self.month_start),
            ('date_order', '<', self.month_end + timedelta(days=1)),
        ]).mapped('amount_untaxed'))
        self.assertAlmostEqual(progress['value'], expected, places=2)
        self.assertAlmostEqual(progress['value'], 600.0, places=2)
        self.assertEqual(progress['target'], 1000.0)
        self.assertAlmostEqual(progress['progress'], 60.0, places=1)

    def test_progress_widget_orders_metric(self):
        dashboard = self.env['dashboard.suite'].create({
            'name': 'Orders Target Check',
        })
        widget = self.env['dashboard.suite.widget'].create({
            'name': 'Orders vs Target',
            'dashboard_id': dashboard.id,
            'model_id': self.env['ir.model']._get('sale.order').id,
            'widget_type': 'progress',
            'operation': 'count',
            'domain': [['state', 'in', ['sale']]],
            'config': {
                'target_source': 'sales_target',
                'target_metric': 'orders',
                'target_date_field': 'date_order',
            },
        })
        payload = dashboard.get_widget_data(widget.id)
        self.assertEqual(payload['value'], 2)
        self.assertEqual(payload['target'], 20.0)
        self.assertAlmostEqual(payload['progress'], 10.0, places=1)

    def test_invalid_target_metric_rejected(self):
        dashboard = self.env['dashboard.suite'].create({
            'name': 'Bad Target Check',
        })
        with self.assertRaises(ValidationError):
            self.env['dashboard.suite.widget'].create({
                'name': 'Bad Metric',
                'dashboard_id': dashboard.id,
                'model_id': self.env['ir.model']._get('sale.order').id,
                'widget_type': 'progress',
                'operation': 'count',
                'config': {
                    'target_source': 'sales_target',
                    'target_metric': 'bogus',
                },
            })

    # ------------------------------------------------------------------
    # Charts and table
    # ------------------------------------------------------------------
    def test_charts_payload(self):
        payload, widgets = self._widget_payloads()
        status = widgets[self._widget_id('widget_sales_by_status')]
        self.assertIn('Sales Order', status['labels'])
        self.assertIn('Quotation', status['labels'])
        trend = widgets[self._widget_id('widget_sales_trend')]
        self.assertTrue(trend['labels'])
        self.assertTrue(all(len(label) == 7 for label in trend['labels']))
        salesperson = widgets[self._widget_id('widget_sales_by_salesperson')]
        self.assertIn(self.env.user.name, salesperson['labels'])
        self.assertAlmostEqual(sum(salesperson['datasets'][0]['data']), 650.0,
                               places=2)

    def test_table_payload(self):
        payload, widgets = self._widget_payloads()
        table = widgets[self._widget_id('widget_sales_latest_orders')]
        self.assertEqual(
            [column['name'] for column in table['columns']],
            ['name', 'partner_id', 'amount_untaxed', 'state', 'date_order'])
        self.assertEqual(table['total'], 4)
        self.assertEqual(len(table['rows']), 4)

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------
    def test_date_filter_limits_data(self):
        date_filter = self.env.ref(
            'dashboard_suite_sales.filter_sales_order_date')
        payload, widgets = self._widget_payloads(
            filters={str(date_filter.id): '2099-01-01'})
        amount_widget = widgets[self._widget_id('widget_sales_confirmed_amount')]
        self.assertEqual(amount_widget['value'], 0)
        progress = widgets[self._widget_id('widget_sales_month_target')]
        self.assertEqual(progress['value'], 0)
        self.assertEqual(progress['target'], 1000.0)

    def test_salesperson_filter(self):
        salesperson_filter = self.env.ref(
            'dashboard_suite_sales.filter_sales_salesperson')
        _, widgets = self._widget_payloads(
            filters={str(salesperson_filter.id): self.viewer.id})
        amount_widget = widgets[self._widget_id('widget_sales_confirmed_amount')]
        self.assertEqual(amount_widget['value'], 0)
        _, widgets = self._widget_payloads(
            filters={str(salesperson_filter.id): self.env.uid})
        amount_widget = widgets[self._widget_id('widget_sales_confirmed_amount')]
        self.assertAlmostEqual(amount_widget['value'], 650.0, places=2)

    def test_filter_without_value_is_ignored(self):
        _, widgets = self._widget_payloads()
        amount_widget = widgets[self._widget_id('widget_sales_confirmed_amount')]
        self.assertAlmostEqual(amount_widget['value'], 650.0, places=2)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def test_viewer_cannot_modify_predefined_dashboard(self):
        widget = self.env.ref('dashboard_suite_sales.widget_sales_confirmed_amount')
        with self.assertRaises(AccessError):
            self.dashboard.with_user(self.viewer).write(
                {'description': 'Hacked'})
        with self.assertRaises(AccessError):
            widget.with_user(self.viewer).write({'name': 'Hacked'})
