from odoo.tests import TransactionCase, new_test_user, tagged

VIEWER_GROUP = 'dashboard_suite_core.group_dashboard_viewer'


@tagged('post_install', '-at_install')
class TestPurchaseDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = cls.env.ref(
            'dashboard_suite_purchase.dashboard_purchase_overview')
        cls.viewer = new_test_user(
            cls.env, login='ds_purchase_viewer',
            groups='base.group_user,purchase.group_purchase_user,'
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

    def test_rfq_counted(self):
        vendor = self.env['res.partner'].create({'name': 'Dash Vendor'})
        product = self.env['product.product'].create({
            'name': 'Dash Purchase Product',
            'type': 'consu',
            'standard_price': 10.0,
        })
        order = self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_qty': 2.0,
                'price_unit': 15.0,
            })],
        })
        widget = self.env.ref(
            'dashboard_suite_purchase.widget_purchase_draft_rfqs')
        values = {
            w['id']: w
            for w in self.dashboard.get_dashboard_data()['widgets']
        }
        expected = self.env['purchase.order'].search_count(
            [['state', 'in', ['draft', 'sent']]])
        self.assertEqual(values[widget.id]['value'], expected)
        self.assertEqual(order.state, 'draft')
