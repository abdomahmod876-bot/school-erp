from odoo.tests import TransactionCase, new_test_user, tagged

VIEWER_GROUP = 'dashboard_suite_core.group_dashboard_viewer'


@tagged('post_install', '-at_install')
class TestInventoryDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = cls.env.ref(
            'dashboard_suite_inventory.dashboard_inventory_overview')
        cls.viewer = new_test_user(
            cls.env, login='ds_inventory_viewer',
            groups='base.group_user,stock.group_stock_user,' + VIEWER_GROUP,
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

    def test_on_hand_units(self):
        product = self.env['product.product'].create({
            'name': 'Dashboard Stock Product',
            'is_storable': True,
        })
        self.env['stock.quant']._update_available_quantity(
            product, self.env.ref('stock.stock_location_stock'), 7.0)
        payload = self.dashboard.get_dashboard_data()
        widget = self.env.ref(
            'dashboard_suite_inventory.widget_inventory_on_hand_units')
        values = {w['id']: w for w in payload['widgets']}
        self.assertGreaterEqual(values[widget.id]['value'], 7.0)
