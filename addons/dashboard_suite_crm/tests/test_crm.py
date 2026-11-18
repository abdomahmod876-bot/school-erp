import base64

from odoo.tests import TransactionCase, new_test_user, tagged

VIEWER_GROUP = 'dashboard_suite_core.group_dashboard_viewer'


@tagged('post_install', '-at_install')
class TestCrmDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = cls.env.ref(
            'dashboard_suite_crm.dashboard_crm_pipeline')
        cls.viewer = new_test_user(
            cls.env, login='ds_crm_viewer',
            groups='base.group_user,sales_team.group_sale_salesman,'
                   + VIEWER_GROUP,
            company_id=cls.env.company.id)

    def test_structure(self):
        self.assertEqual(self.dashboard.dashboard_type, 'predefined')
        self.assertEqual(len(self.dashboard.widget_ids), 7)
        self.assertEqual(len(self.dashboard.filter_ids), 2)

    def test_viewer_payload(self):
        payload = self.dashboard.with_user(self.viewer).get_dashboard_data()
        self.assertEqual(len(payload['widgets']), 7)
        self.assertFalse([w for w in payload['widgets'] if w.get('error')])
        self.assertEqual(
            {w['widget_type'] for w in payload['widgets']},
            {'kpi', 'chart', 'table'})

    def test_table_export(self):
        table = self.dashboard.widget_ids.filtered(
            lambda widget: widget.widget_type == 'table')
        export = self.dashboard.with_user(self.viewer).export_widget_data(
            table.id)
        self.assertTrue(base64.b64decode(export['content']))


class TestCrmData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = cls.env.ref(
            'dashboard_suite_crm.dashboard_crm_pipeline')

    def test_opportunities_counted(self):
        lead_model = self.env['crm.lead']
        before = self.dashboard.get_dashboard_data()
        kpi_ids = {widget['id']: widget for widget in before['widgets']}
        open_widget = self.env.ref(
            'dashboard_suite_crm.widget_crm_open_opportunities')
        previous = kpi_ids[open_widget.id]['value']
        lead_model.create([
            {'name': 'Dashboard Opp A', 'type': 'opportunity',
             'expected_revenue': 500.0},
            {'name': 'Dashboard Opp B', 'type': 'opportunity',
             'expected_revenue': 750.0},
            {'name': 'Dashboard Lead C', 'type': 'lead'},
        ])
        after = {
            widget['id']: widget
            for widget in self.dashboard.get_dashboard_data()['widgets']
        }
        self.assertEqual(after[open_widget.id]['value'], previous + 2)
        revenue_widget = self.env.ref(
            'dashboard_suite_crm.widget_crm_expected_revenue')
        self.assertEqual(kpi_ids[revenue_widget.id]['value'] + 1250.0,
                         after[revenue_widget.id]['value'])
