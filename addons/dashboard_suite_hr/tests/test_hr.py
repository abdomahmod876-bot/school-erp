from odoo.tests import TransactionCase, new_test_user, tagged

VIEWER_GROUP = 'dashboard_suite_core.group_dashboard_viewer'


@tagged('post_install', '-at_install')
class TestHrDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = cls.env.ref('dashboard_suite_hr.dashboard_hr_overview')
        cls.viewer = new_test_user(
            cls.env, login='ds_hr_viewer',
            groups='base.group_user,hr.group_hr_user,' + VIEWER_GROUP,
            company_id=cls.env.company.id)

    def test_structure(self):
        self.assertEqual(self.dashboard.dashboard_type, 'predefined')
        self.assertEqual(len(self.dashboard.widget_ids), 7)
        self.assertEqual(len(self.dashboard.filter_ids), 1)

    def test_viewer_payload(self):
        payload = self.dashboard.with_user(self.viewer).get_dashboard_data()
        self.assertEqual(len(payload['widgets']), 7)
        self.assertFalse([w for w in payload['widgets'] if w.get('error')])
        self.assertEqual(
            {w['widget_type'] for w in payload['widgets']},
            {'kpi', 'chart', 'table'})

    def test_headcount(self):
        department = self.env['hr.department'].create({'name': 'Dash Dept'})
        self.env['hr.employee'].create([
            {'name': 'Dash Employee A', 'department_id': department.id},
            {'name': 'Dash Employee B', 'department_id': department.id},
        ])
        payload = self.dashboard.get_dashboard_data()
        values = {w['id']: w for w in payload['widgets']}
        employees = self.env.ref('dashboard_suite_hr.widget_hr_employees')
        self.assertGreaterEqual(values[employees.id]['value'], 2)
        by_department = self.env.ref(
            'dashboard_suite_hr.widget_hr_by_department')
        labels = dict(zip(
            values[by_department.id]['labels'],
            values[by_department.id]['datasets'][0]['data']))
        self.assertGreaterEqual(labels.get('Dash Dept', 0), 2)
