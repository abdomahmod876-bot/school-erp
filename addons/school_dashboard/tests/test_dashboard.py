from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user


class TestSchoolDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        cls.country_eg = cls.env.ref('base.eg')
        cls.partners = cls.env['res.partner'].create([
            {
                'name': 'DashTest Alpha',
                'company_type': 'company',
                'country_id': cls.country_eg.id,
            },
            {
                'name': 'DashTest Beta',
                'company_type': 'company',
                'country_id': cls.country_eg.id,
            },
            {
                'name': 'DashTest Gamma',
                'company_type': 'person',
            },
        ])
        cls.base_domain = [('id', 'in', cls.partners.ids)]

    def _item_values(self, **values):
        defaults = {
            'name': 'Item',
            'item_type': 'tile',
            'model_id': self.partner_model.id,
            'measure': 'count',
            'domain': str(self.base_domain),
        }
        defaults.update(values)
        return defaults

    def _create_dashboard(self, items=None):
        return self.env['school.dashboard'].create({
            'name': 'Test Dashboard',
            'item_ids': [(0, 0, values) for values in (items or [])],
        })

    def _single_item_data(self, **values):
        dashboard = self._create_dashboard([self._item_values(**values)])
        data = dashboard.get_dashboard_data()
        self.assertEqual(len(data['items']), 1)
        return data['items'][0]

    def test_scalar_count(self):
        item = self._single_item_data(name='Total')
        self.assertFalse(item.get('error'))
        self.assertEqual(item['kind'], 'scalar')
        self.assertEqual(item['value'], 3)

    def test_scalar_domain_filter(self):
        item = self._single_item_data(
            name='Companies',
            domain=str(self.base_domain + [('is_company', '=', True)]),
        )
        self.assertEqual(item['value'], 2)

    def test_chart_group_by_boolean(self):
        field = self.env['ir.model.fields']._get('res.partner', 'is_company')
        item = self._single_item_data(
            name='Types',
            item_type='pie',
            groupby_field_id=field.id,
        )
        self.assertFalse(item.get('error'))
        self.assertEqual(item['kind'], 'chart')
        values = dict(zip(item['labels'], item['values']))
        self.assertEqual(values.get('Yes'), 2)
        self.assertEqual(values.get('No'), 1)
        self.assertEqual(item['total'], 3)

    def test_chart_group_by_many2one(self):
        field = self.env['ir.model.fields']._get('res.partner', 'country_id')
        item = self._single_item_data(
            name='Countries',
            item_type='bar',
            groupby_field_id=field.id,
        )
        self.assertFalse(item.get('error'))
        values = dict(zip(item['labels'], item['values']))
        self.assertEqual(values.get('Egypt'), 2)

    def test_chart_monthly_series(self):
        field = self.env['ir.model.fields']._get('res.partner', 'create_date')
        item = self._single_item_data(
            name='Trend',
            item_type='line',
            date_field_id=field.id,
        )
        self.assertFalse(item.get('error'))
        self.assertEqual(sum(item['values']), 3)

    def test_list_item(self):
        name_field = self.env['ir.model.fields']._get('res.partner', 'name')
        email_field = self.env['ir.model.fields']._get('res.partner', 'email')
        item = self._single_item_data(
            name='Rows',
            item_type='list',
            list_field_ids=[(6, 0, [name_field.id, email_field.id])],
        )
        self.assertFalse(item.get('error'))
        self.assertEqual(item['kind'], 'list')
        self.assertEqual([column['name'] for column in item['columns']], ['name', 'email'])
        self.assertEqual(len(item['rows']), 3)
        self.assertIn('DashTest Alpha', [row[0] for row in item['rows']])

    def test_invalid_domain_returns_error(self):
        item = self._single_item_data(name='Broken', domain='[(')
        self.assertTrue(item.get('error'))

    def test_date_filter(self):
        field = self.env['ir.model.fields']._get('res.partner', 'create_date')
        dashboard = self._create_dashboard([
            self._item_values(name='Dated', date_field_id=field.id),
        ])
        today = str(date.today())
        data = dashboard.get_dashboard_data(date_from=today, date_to=today)
        self.assertEqual(data['items'][0]['value'], 3)
        data = dashboard.get_dashboard_data(date_from='2000-01-01', date_to='2000-01-02')
        self.assertEqual(data['items'][0]['value'], 0)

    def test_set_item_order(self):
        dashboard = self._create_dashboard([
            self._item_values(name='First', sequence=10),
            self._item_values(name='Second', sequence=20),
            self._item_values(name='Third', sequence=30),
        ])
        first, second, third = dashboard.item_ids
        dashboard.set_item_order([third.id, first.id, second.id])
        data = dashboard.get_dashboard_data()
        self.assertEqual(
            [item['name'] for item in data['items']],
            ['Third', 'First', 'Second'])
        second.span = '12'
        data = dashboard.get_dashboard_data()
        spans = {item['name']: item['span'] for item in data['items']}
        self.assertEqual(spans['Second'], 12)
        other = self._create_dashboard([self._item_values(name='Foreign')])
        with self.assertRaises(UserError):
            dashboard.set_item_order([other.item_ids.id])

    def test_owner_and_shared_access(self):
        user_b = new_test_user(
            self.env, login='dash_user_b', groups='school_core.group_school_user')
        dashboard = self._create_dashboard([self._item_values(name='Private')])
        Dashboard = self.env['school.dashboard']
        self.assertEqual(
            Dashboard.with_user(user_b).search_count([('id', '=', dashboard.id)]), 0)
        with self.assertRaises(AccessError):
            dashboard.with_user(user_b).read(['name'])
        dashboard.group_ids = [(4, self.env.ref('school_core.group_school_user').id)]
        self.assertEqual(
            Dashboard.with_user(user_b).search_count([('id', '=', dashboard.id)]), 1)
        data = dashboard.with_user(user_b).get_dashboard_data()
        self.assertEqual(len(data['items']), 1)
