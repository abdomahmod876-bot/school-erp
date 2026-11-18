import base64
import csv
import io
import unittest
from datetime import date, datetime

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.dashboard_suite_core.models.domain_validator import (
    combine_domains, validate_domain)

GROUP_VIEWER = 'dashboard_suite_core.group_dashboard_viewer'


@tagged('post_install', '-at_install')
class TestDashboardEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'sale.order' not in cls.env:
            raise unittest.SkipTest('sale is required for the engine tests')
        cls.company = cls.env.company
        cls.so_model = cls.env['sale.order']
        cls.so_model_meta = cls.env['ir.model']._get('sale.order')
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Dashboard Engine Partner',
            'email': 'engine@example.com',
        })
        cls.other_partner = cls.env['res.partner'].create({
            'name': 'Dashboard Engine Other',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Dashboard Engine Product',
            'list_price': 100.0,
            'taxes_id': [(5, 0, 0)],
        })
        cls.dashboard = cls.env['dashboard.suite'].create({
            'name': 'Engine Dashboard',
            'sequence': 1,
        })
        cls.sales_user = new_test_user(
            cls.env, login='ds_engine_sales',
            groups='base.group_user,sales_team.group_sale_salesman,' + GROUP_VIEWER,
            company_id=cls.company.id)
        cls.blind_user = new_test_user(
            cls.env, login='ds_engine_blind',
            groups='base.group_user,' + GROUP_VIEWER,
            company_id=cls.company.id)
        cls.editor_user = new_test_user(
            cls.env, login='ds_engine_editor',
            groups='base.group_user,dashboard_suite_core.group_dashboard_editor',
            company_id=cls.company.id)

        cls.env['dashboard.suite.access'].create({
            'dashboard_id': cls.dashboard.id,
            'user_id': cls.sales_user.id,
            'access_level': 'viewer',
        })
        cls.env['dashboard.suite.access'].create({
            'dashboard_id': cls.dashboard.id,
            'user_id': cls.blind_user.id,
            'access_level': 'viewer',
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_widget(self, model=None, **values):
        defaults = {
            'name': 'Engine Widget',
            'dashboard_id': self.dashboard.id,
            'model_id': (model or self.so_model_meta).id,
            'widget_type': 'kpi',
            'operation': 'count',
            'domain': [],
        }
        defaults.update(values)
        return self.env['dashboard.suite.widget'].create(defaults)

    def _create_order(self, price, partner=None, user=None, currency=None,
                      state='draft', date_order=None):
        vals = {
            'partner_id': (partner or self.partner).id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': price,
                'tax_ids': [(5, 0, 0)],
            })],
        }
        if user:
            vals['user_id'] = user.id
        if currency:
            vals['currency_id'] = currency.id
        order = self.so_model.create(vals)
        if currency:
            order.write({'currency_id': currency.id})
            order.order_line.write({'price_unit': price})
        if date_order:
            order.write({'date_order': date_order})
        if state == 'sale':
            order.action_confirm()
        return order

    def _partner_domain(self, partner=None):
        return [['partner_id', '=', (partner or self.partner).id]]

    # ------------------------------------------------------------------
    # KPI
    # ------------------------------------------------------------------
    def test_kpi_count(self):
        self._create_order(100.0)
        self._create_order(250.0)
        self._create_order(400.0, state='sale')
        widget = self._create_widget(domain=self._partner_domain())
        payload = self.dashboard.get_widget_data(widget.id)
        expected = self.so_model.search_count(self._partner_domain())
        self.assertEqual(payload['value'], expected)
        self.assertEqual(payload['widget_type'], 'kpi')
        self.assertNotIn('error', payload)
        self.assertIsNone(payload['currency'])

    def test_kpi_sum_measure(self):
        self._create_order(100.0)
        self._create_order(250.0)
        amount_field = self.env['ir.model.fields']._get(
            'sale.order', 'amount_total')
        widget = self._create_widget(
            domain=self._partner_domain(),
            operation='sum', measure_field_id=amount_field.id)
        payload = self.dashboard.get_widget_data(widget.id)
        orders = self.so_model.search(self._partner_domain())
        self.assertAlmostEqual(
            payload['value'], sum(orders.mapped('amount_total')), places=2)
        self.assertEqual(payload['measure']['operation'], 'sum')
        self.assertEqual(payload['currency']['id'], self.company.currency_id.id)

    def test_kpi_domain_filtering(self):
        self._create_order(100.0)
        self._create_order(250.0, state='sale')
        widget = self._create_widget(
            domain=[['partner_id', '=', self.partner.id],
                    ['state', '=', 'sale']])
        payload = self.dashboard.get_widget_data(widget.id)
        expected = self.so_model.search_count([
            ['partner_id', '=', self.partner.id],
            ['state', '=', 'sale'],
        ])
        self.assertEqual(payload['value'], expected)

    def test_progress_requires_target(self):
        with self.assertRaises(ValidationError):
            self._create_widget(widget_type='progress')
        self._create_order(100.0)
        widget = self._create_widget(
            widget_type='progress', domain=self._partner_domain(),
            config={'target': 10})
        payload = self.dashboard.get_widget_data(widget.id)
        expected = self.so_model.search_count(self._partner_domain())
        self.assertEqual(payload['value'], expected)
        self.assertEqual(payload['target'], 10.0)
        self.assertAlmostEqual(payload['progress'], expected * 10.0, places=1)

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------
    def test_chart_group_by_selection(self):
        self._create_order(100.0)
        self._create_order(250.0)
        self._create_order(400.0, state='sale')
        state_field = self.env['ir.model.fields']._get('sale.order', 'state')
        widget = self._create_widget(
            widget_type='chart', chart_type='bar',
            group_by_field_id=state_field.id,
            domain=self._partner_domain())
        payload = self.dashboard.get_widget_data(widget.id)
        self.assertEqual(len(payload['labels']), len(payload['datasets'][0]['data']))
        self.assertTrue(payload['labels'])
        self.assertEqual(
            sum(payload['datasets'][0]['data']),
            self.so_model.search_count(self._partner_domain()))

    def test_chart_group_by_many2one(self):
        self._create_order(100.0)
        self._create_order(100.0, partner=self.other_partner)
        partner_field = self.env['ir.model.fields']._get(
            'sale.order', 'partner_id')
        widget = self._create_widget(
            widget_type='chart', chart_type='pie',
            group_by_field_id=partner_field.id,
            domain=[['partner_id', 'in', [
                self.partner.id, self.other_partner.id]]])
        payload = self.dashboard.get_widget_data(widget.id)
        labels = payload['labels']
        self.assertIn(self.partner.display_name, labels)
        self.assertIn(self.other_partner.display_name, labels)

    def test_chart_date_granularity(self):
        self._create_order(
            100.0, date_order=fields.Datetime.to_datetime(
                '2026-01-15 10:00:00'))
        date_field = self.env['ir.model.fields']._get(
            'sale.order', 'date_order')
        widget = self._create_widget(
            widget_type='chart', chart_type='line',
            date_field_id=date_field.id, config={'granularity': 'month'},
            domain=self._partner_domain())
        payload = self.dashboard.get_widget_data(widget.id)
        self.assertIn('2026-01', payload['labels'])
        self.assertEqual(payload['group_by']['granularity'], 'month')

    def test_chart_requires_group_or_date(self):
        with self.assertRaises(ValidationError):
            self._create_widget(widget_type='chart', chart_type='bar')

    def test_invalid_granularity(self):
        date_field = self.env['ir.model.fields']._get(
            'sale.order', 'date_order')
        with self.assertRaises(ValidationError):
            self._create_widget(
                widget_type='chart', chart_type='line',
                date_field_id=date_field.id, config={'granularity': 'hour'})

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------
    def test_table_pagination_and_total(self):
        self.env['res.partner'].create([
            {'name': f'DashPage Partner {index}'} for index in range(5)
        ])
        widget = self._create_widget(
            model=self.partner_model,
            widget_type='table',
            domain=[['name', 'ilike', 'DashPage Partner']],
            limit=2,
            config={'columns': ['display_name', 'email']})
        first = self.dashboard.get_widget_data(widget.id)
        self.assertEqual(first['total'], 5)
        self.assertEqual(len(first['rows']), 2)
        self.assertTrue(first['has_more'])
        self.assertEqual(
            first['columns'][0]['name'], 'display_name')
        second = self.dashboard.get_widget_data(widget.id, offset=2)
        self.assertEqual(len(second['rows']), 2)
        self.assertNotEqual(
            [row['id'] for row in first['rows']],
            [row['id'] for row in second['rows']])
        last = self.dashboard.get_widget_data(widget.id, offset=4)
        self.assertEqual(len(last['rows']), 1)
        self.assertFalse(last['has_more'])
        self.assertEqual(
            set(last['rows'][0]['values']), {'display_name', 'email'})

    def test_table_search(self):
        self.env['res.partner'].create([
            {'name': 'DashSearch Alpha'},
            {'name': 'DashSearch Beta'},
        ])
        widget = self._create_widget(
            model=self.partner_model, widget_type='table',
            domain=[['name', 'ilike', 'DashSearch']],
            config={'columns': ['display_name']})
        payload = self.dashboard.get_widget_data(
            widget.id, search='Beta')
        self.assertEqual(payload['total'], 1)
        self.assertEqual(len(payload['rows']), 1)

    def test_table_rejects_binary_column(self):
        with self.assertRaises(ValidationError):
            self._create_widget(
                model=self.partner_model, widget_type='table',
                config={'columns': ['image_1920']})

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _read_csv(self, export):
        content = base64.b64decode(export['content']).decode('utf-8-sig')
        return list(csv.reader(io.StringIO(content)))

    def test_export_table_csv(self):
        self.env['res.partner'].create([
            {'name': f'DashExport Partner {index}'} for index in range(3)
        ])
        widget = self._create_widget(
            model=self.partner_model, widget_type='table',
            domain=[['name', 'ilike', 'DashExport Partner']],
            config={'columns': ['display_name', 'email']})
        export = self.dashboard.export_widget_data(widget.id)
        self.assertEqual(export['mimetype'], 'text/csv')
        self.assertTrue(export['filename'].endswith('.csv'))
        self.assertIn('Engine-Widget', export['filename'])
        rows = self._read_csv(export)
        self.assertEqual(rows[0], ['Display Name', 'Email'])
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            sorted(row[0] for row in rows[1:]),
            [f'DashExport Partner {index}' for index in range(3)])

    def test_export_table_respects_search(self):
        self.env['res.partner'].create([
            {'name': 'DashExportSearch Alpha'},
            {'name': 'DashExportSearch Beta'},
        ])
        widget = self._create_widget(
            model=self.partner_model, widget_type='table',
            domain=[['name', 'ilike', 'DashExportSearch']],
            config={'columns': ['display_name']})
        rows = self._read_csv(
            self.dashboard.export_widget_data(widget.id, search='Beta'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], 'DashExportSearch Beta')

    def test_export_chart_csv(self):
        self._create_order(100.0)
        widget = self._create_widget(
            widget_type='chart', chart_type='bar',
            group_by_field_id=self.env['ir.model.fields']._get(
                'sale.order', 'user_id').id,
            domain=self._partner_domain())
        rows = self._read_csv(self.dashboard.export_widget_data(widget.id))
        self.assertEqual(rows[0], ['Salesperson', 'Count'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(int(rows[1][1]), 1)

    def test_export_rejects_foreign_and_non_data_widgets(self):
        table = self._create_widget(
            model=self.partner_model, widget_type='table',
            config={'columns': ['display_name']})
        kpi = self._create_widget(domain=self._partner_domain())
        with self.assertRaises(UserError):
            self.dashboard.export_widget_data(kpi.id)
        other = self.env['dashboard.suite'].create({'name': 'Export Other'})
        with self.assertRaises(AccessError):
            other.export_widget_data(table.id)

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    def test_record_rules_enforced(self):
        self._create_order(100.0, user=self.sales_user)
        self._create_order(200.0, user=self.env.user)
        widget = self._create_widget(domain=self._partner_domain())
        payload = self.dashboard.with_user(self.sales_user).get_widget_data(
            widget.id)
        expected = self.so_model.with_user(self.sales_user).search_count(
            self._partner_domain())
        self.assertEqual(payload['value'], expected)
        admin_value = self.dashboard.get_widget_data(widget.id)['value']
        self.assertLess(payload['value'], admin_value)

    def test_model_access_denied(self):
        widget = self._create_widget(domain=self._partner_domain())
        with self.assertRaises(AccessError):
            self.dashboard.with_user(self.blind_user).get_widget_data(widget.id)
        payload = self.dashboard.with_user(
            self.blind_user).get_dashboard_data()
        self.assertIn('error', payload['widgets'][0])

    def test_widget_of_other_dashboard(self):
        other = self.env['dashboard.suite'].create({'name': 'Other'})
        widget = self.env['dashboard.suite.widget'].create({
            'name': 'Foreign',
            'dashboard_id': other.id,
            'model_id': self.partner_model.id,
            'widget_type': 'kpi',
            'operation': 'count',
        })
        with self.assertRaises(AccessError):
            self.dashboard.get_widget_data(widget.id)

    def test_domain_injection_is_parameterized(self):
        widget = self._create_widget(
            model=self.partner_model,
            domain=[['display_name', '=', "x' OR 1=1 --"]])
        payload = self.dashboard.get_widget_data(widget.id)
        self.assertEqual(payload['value'], 0)
        self.assertTrue(self.env['res.partner'].search_count([]) >= 0)

    # ------------------------------------------------------------------
    # Domain validator
    # ------------------------------------------------------------------
    def test_domain_validator(self):
        partner_model = self.env['res.partner']
        self.assertEqual(
            validate_domain(partner_model, [['name', '=', 'x']]),
            [['name', '=', 'x']])
        self.assertEqual(
            validate_domain(partner_model, ['|', ['name', '=', 'x'],
                                            ['email', '=', 'y']]),
            ['|', ['name', '=', 'x'], ['email', '=', 'y']])
        self.assertEqual(
            combine_domains([['a', '=', 1]], [['b', '=', 2]]),
            ['&', ['a', '=', 1], ['b', '=', 2]])
        self.assertEqual(
            validate_domain(
                partner_model, [['country_id.name', 'ilike', 'x']]),
            [['country_id.name', 'ilike', 'x']])
        for bad_domain in (
                [['unknown_field', '=', 1]],
                [['country_id.missing', '=', 1]],
                [['name.missing', '=', 1]],
                [['name', 'sql', 'x']],
                [['name']],
                ['|', ['name', '=', 'x']],
                [['name', '=', 'x'], '|'],
                [['name', 'set', 1]],
                42,
                'not-a-domain'):
            with self.assertRaises(ValidationError, msg=bad_domain):
                validate_domain(partner_model, bad_domain)

    # ------------------------------------------------------------------
    # Currency
    # ------------------------------------------------------------------
    def test_currency_conversion(self):
        eur = self.env['res.currency'].create({
            'name': 'DSX', 'symbol': 'X', 'rounding': 0.01,
        })
        self.env['res.currency.rate'].create({
            'currency_id': eur.id,
            'name': fields.Date.to_date('2020-01-01'),
            'rate': 0.5,
            'company_id': self.company.id,
        })
        partner = self.env['res.partner'].create({'name': 'Dash Currency Partner'})
        self._create_order(50.0, partner=partner)
        eur_order = self._create_order(100.0, partner=partner, currency=eur)
        amount_field = self.env['ir.model.fields']._get(
            'sale.order', 'amount_total')
        widget = self._create_widget(
            operation='sum', measure_field_id=amount_field.id,
            domain=[['partner_id', '=', partner.id]])
        payload = self.dashboard.get_widget_data(widget.id)
        today = fields.Date.context_today(self.so_model)
        expected = 50.0 + eur._convert(
            100.0, self.company.currency_id, self.company, today)
        self.assertAlmostEqual(payload['value'], expected, places=2)
        self.assertEqual(payload['currency']['id'], self.company.currency_id.id)
        self.assertAlmostEqual(eur_order.amount_total, 100.0, places=2)

    # ------------------------------------------------------------------
    # Filters and options
    # ------------------------------------------------------------------
    def test_dashboard_filters(self):
        self._create_order(100.0)
        date_field = self.env['ir.model.fields']._get(
            'sale.order', 'date_order')
        dashboard_filter = self.env['dashboard.suite.filter'].create({
            'name': 'Order date',
            'dashboard_id': self.dashboard.id,
            'filter_type': 'date',
            'field_id': date_field.id,
            'operator': '>=',
            'default_value': {'value': '2030-01-01'},
        })
        widget = self._create_widget(domain=self._partner_domain())
        payload = self.dashboard.get_dashboard_data()
        self.assertEqual(len(payload['filters']), 1)
        self.assertEqual(payload['filters'][0]['id'], dashboard_filter.id)
        self.assertEqual(payload['widgets'][0]['value'], 0)
        overridden = self.dashboard.get_dashboard_data(
            filters={str(dashboard_filter.id): '2026-01-01'})
        expected = self.so_model.search_count(
            self._partner_domain() + [['date_order', '>=', '2026-01-01']])
        self.assertEqual(overridden['widgets'][0]['value'], expected)
        with self.assertRaises(AccessError):
            self.dashboard.with_user(
                self.env['res.users'].browse(
                    self.env.ref('base.public_user').id)
            ).get_dashboard_data()

    def test_filter_without_default_value_is_ignored(self):
        orders = self.so_model.search_count(self._partner_domain())
        date_field = self.env['ir.model.fields']._get(
            'sale.order', 'date_order')
        self.env['dashboard.suite.filter'].create({
            'name': 'Optional date',
            'dashboard_id': self.dashboard.id,
            'filter_type': 'date',
            'field_id': date_field.id,
            'operator': '>=',
        })
        widget = self._create_widget(domain=self._partner_domain())
        payload = self.dashboard.get_dashboard_data()
        self.assertEqual(payload['widgets'][0]['value'], orders)
        self.assertEqual(len(payload['filters']), 1)

    def test_required_filter_raises(self):
        date_field = self.env['ir.model.fields']._get(
            'sale.order', 'date_order')
        self.env['dashboard.suite.filter'].create({
            'name': 'Required date',
            'dashboard_id': self.dashboard.id,
            'filter_type': 'date',
            'field_id': date_field.id,
            'operator': '>=',
            'is_required': True,
        })
        widget = self._create_widget(domain=self._partner_domain())
        with self.assertRaises(UserError):
            self.dashboard.get_widget_data(widget.id)

    def test_filter_options(self):
        state_field = self.env['ir.model.fields']._get('sale.order', 'state')
        selection_filter = self.env['dashboard.suite.filter'].create({
            'name': 'State',
            'dashboard_id': self.dashboard.id,
            'filter_type': 'selection',
            'field_id': state_field.id,
        })
        options = self.dashboard.get_filter_options(selection_filter.id)
        self.assertEqual(options['type'], 'selection')
        self.assertTrue(options['options'])
        self.assertIn(
            'draft', [option['value'] for option in options['options']])
        partner_field = self.env['ir.model.fields']._get(
            'sale.order', 'partner_id')
        relation_filter = self.env['dashboard.suite.filter'].create({
            'name': 'Partner',
            'dashboard_id': self.dashboard.id,
            'filter_type': 'many2one',
            'field_id': partner_field.id,
        })
        relation_options = self.dashboard.get_filter_options(
            relation_filter.id, limit=5)
        self.assertEqual(relation_options['type'], 'many2one')
        self.assertTrue(relation_options['options'])

    def test_many2one_filter_accepts_string_id(self):
        partner_field = self.env['ir.model.fields']._get(
            'sale.order', 'partner_id')
        dashboard_filter = self.env['dashboard.suite.filter'].create({
            'name': 'Partner',
            'dashboard_id': self.dashboard.id,
            'filter_type': 'many2one',
            'field_id': partner_field.id,
        })
        self._create_order(100.0)
        self._create_order(200.0, partner=self.other_partner)
        widget = self._create_widget(domain=[])
        data = self.dashboard.get_dashboard_data(
            filters={dashboard_filter.id: str(self.partner.id)})
        self.assertEqual(data['widgets'][0]['value'], 1)
        self.assertEqual(
            data['filters'][0]['default_value'], str(self.partner.id))

    # ------------------------------------------------------------------
    # Client action entry points (Phase 3)
    # ------------------------------------------------------------------
    def test_action_open_returns_client_action(self):
        action = self.dashboard.action_open()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'dashboard_suite_core.dashboard_action')
        self.assertEqual(action['params']['dashboard_id'], self.dashboard.id)

    def test_default_dashboard_data(self):
        self._create_widget()
        preferred = self.env['dashboard.suite'].create({
            'name': 'Preferred Dashboard',
            'is_default': True,
        })
        data = self.env['dashboard.suite'].get_default_dashboard_data()
        self.assertEqual(data['id'], preferred.id)
        self.assertTrue(data['can_edit'])
        self.assertEqual(
            self.env['dashboard.suite']._find_default_dashboard(), preferred)

    def test_default_dashboard_respects_access(self):
        self.env['dashboard.suite'].create({
            'name': 'Manager Only Default',
            'is_default': True,
        })
        self._create_widget()
        data = self.env['dashboard.suite'].with_user(
            self.sales_user).get_default_dashboard_data()
        self.assertEqual(data['id'], self.dashboard.id)
        self.assertEqual(data['access_level'], 'viewer')
        self.assertFalse(data['can_edit'])

    # ------------------------------------------------------------------
    # Layout persistence (Phase 4)
    # ------------------------------------------------------------------
    def test_save_layout_persists_and_clamps(self):
        first = self._create_widget(name='First', width=3, height=1)
        second = self._create_widget(name='Second', width=3, height=1)
        self.dashboard.save_layout([
            {'id': second.id, 'sequence': 10, 'width': 6, 'height': 2},
            {'id': first.id, 'sequence': 20, 'width': 99, 'height': 0},
        ])
        self.assertEqual(second.sequence, 10)
        self.assertEqual(second.width, 6)
        self.assertEqual(second.height, 2)
        self.assertEqual(first.sequence, 20)
        self.assertEqual(first.width, 12)
        self.assertEqual(first.height, 1)

    def test_save_layout_rejects_invalid_payloads(self):
        widget = self._create_widget()
        other = self.env['dashboard.suite'].create({'name': 'Other'})
        foreign = self._create_widget(dashboard_id=other.id)
        with self.assertRaises(AccessError):
            self.dashboard.save_layout([{'id': foreign.id, 'sequence': 10}])
        with self.assertRaises(UserError):
            self.dashboard.save_layout([{'id': widget.id}, {'id': widget.id}])
        with self.assertRaises(UserError):
            self.dashboard.save_layout('not-a-list')
        with self.assertRaises(UserError):
            self.dashboard.save_layout([{'id': widget.id, 'width': 'abc'}])

    def test_save_layout_access_control(self):
        widget = self._create_widget()
        with self.assertRaises(AccessError):
            self.dashboard.with_user(self.sales_user).save_layout(
                [{'id': widget.id, 'width': 5}])
        editor_dashboard = self.env['dashboard.suite'].with_user(
            self.editor_user).create({'name': 'Editor Layout'})
        editor_widget = self._create_widget(dashboard_id=editor_dashboard.id)
        editor_dashboard.with_user(self.editor_user).save_layout([
            {'id': editor_widget.id, 'sequence': 10, 'width': 2, 'height': 1},
        ])
        self.assertEqual(editor_widget.width, 2)
        predefined = self.env['dashboard.suite'].create({
            'name': 'Predefined Layout',
            'dashboard_type': 'predefined',
        })
        predefined_widget = self._create_widget(dashboard_id=predefined.id)
        self.env['dashboard.suite.access'].create({
            'dashboard_id': predefined.id,
            'user_id': self.editor_user.id,
            'access_level': 'editor',
        })
        with self.assertRaises(AccessError):
            predefined.with_user(self.editor_user).save_layout(
                [{'id': predefined_widget.id, 'width': 6}])
