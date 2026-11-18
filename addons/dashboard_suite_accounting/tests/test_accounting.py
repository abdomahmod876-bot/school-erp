from odoo.tests import TransactionCase, new_test_user, tagged

VIEWER_GROUP = 'dashboard_suite_core.group_dashboard_viewer'


@tagged('post_install', '-at_install')
class TestAccountingDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = cls.env.ref(
            'dashboard_suite_accounting.dashboard_accounting_overview')
        cls.viewer = new_test_user(
            cls.env, login='ds_accounting_viewer',
            groups='base.group_user,account.group_account_invoice,'
                   + VIEWER_GROUP,
            company_id=cls.env.company.id)

    def test_structure(self):
        self.assertEqual(self.dashboard.dashboard_type, 'predefined')
        self.assertEqual(len(self.dashboard.widget_ids), 8)
        self.assertEqual(len(self.dashboard.filter_ids), 2)

    def test_viewer_payload(self):
        payload = self.dashboard.with_user(self.viewer).get_dashboard_data()
        self.assertEqual(len(payload['widgets']), 8)
        self.assertFalse([w for w in payload['widgets'] if w.get('error')])
        self.assertEqual(
            {w['widget_type'] for w in payload['widgets']},
            {'kpi', 'chart', 'table'})

    def test_kpi_values_match_orm(self):
        payload = self.dashboard.get_dashboard_data()
        values = {w['id']: w for w in payload['widgets']}
        widget = self.env.ref(
            'dashboard_suite_accounting.widget_accounting_customer_invoices')
        groups = self.env['account.move']._read_group(
            [['move_type', '=', 'out_invoice'], ['state', '=', 'posted']],
            aggregates=['amount_total:sum'])
        expected_amount = groups[0][0] if groups else 0
        self.assertAlmostEqual(
            values[widget.id]['value'], expected_amount or 0, places=2)
        draft_widget = self.env.ref(
            'dashboard_suite_accounting.widget_accounting_draft_invoices')
        expected_drafts = self.env['account.move'].search_count([
            ['move_type', 'in', ['out_invoice', 'in_invoice']],
            ['state', '=', 'draft']])
        self.assertEqual(values[draft_widget.id]['value'], expected_drafts)
