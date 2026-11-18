from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

GROUP_VIEWER = 'dashboard_suite_core.group_dashboard_viewer'
GROUP_EDITOR = 'dashboard_suite_core.group_dashboard_editor'
GROUP_MANAGER = 'dashboard_suite_core.group_dashboard_manager'


@tagged('post_install', '-at_install')
class TestDashboardSuiteCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        cls.company_1 = cls.env.company
        cls.company_2 = cls.env['res.company'].create({'name': 'Dashboard Co 2'})
        cls.viewer = new_test_user(
            cls.env, login='ds_viewer',
            groups='base.group_user,' + GROUP_VIEWER)
        cls.editor = new_test_user(
            cls.env, login='ds_editor',
            groups='base.group_user,' + GROUP_EDITOR)
        cls.manager = new_test_user(
            cls.env, login='ds_manager',
            groups='base.group_user,' + GROUP_MANAGER)
        cls.outsider = new_test_user(
            cls.env, login='ds_outsider', groups='base.group_user')
        cls.company_2_user = new_test_user(
            cls.env, login='ds_company2',
            groups='base.group_user,' + GROUP_EDITOR,
            company_id=cls.company_2.id)
        cls.company_2_user.company_ids = [(6, 0, [cls.company_2.id])]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_dashboard(self, **values):
        defaults = {'name': 'Test Dashboard'}
        defaults.update(values)
        return self.env['dashboard.suite'].create(defaults)

    def _create_widget(self, dashboard, **values):
        defaults = {
            'name': 'Test Widget',
            'dashboard_id': dashboard.id,
            'model_id': self.partner_model.id,
            'widget_type': 'kpi',
            'operation': 'count',
            'domain': [],
        }
        defaults.update(values)
        return self.env['dashboard.suite.widget'].create(defaults)

    def _share(self, dashboard, **values):
        defaults = {
            'dashboard_id': dashboard.id,
            'access_level': 'viewer',
        }
        defaults.update(values)
        return self.env['dashboard.suite.access'].create(defaults)

    # ------------------------------------------------------------------
    # Dashboard lifecycle
    # ------------------------------------------------------------------
    def test_create_defaults(self):
        dashboard = self._create_dashboard()
        self.assertEqual(dashboard.user_id, self.env.user)
        self.assertEqual(dashboard.visibility, 'private')
        self.assertEqual(dashboard.dashboard_type, 'dynamic')
        self.assertEqual(dashboard.company_ids, self.company_1)
        self.assertFalse(dashboard.is_default)
        self.assertFalse(dashboard.is_favorite)

    def test_duplicate_resets_sharing(self):
        dashboard = self._create_dashboard(
            user_id=self.editor.id, description='Original')
        self._create_widget(dashboard)
        self.env['dashboard.suite.filter'].create({
            'name': 'Date',
            'dashboard_id': dashboard.id,
            'filter_type': 'date',
            'field_id': self.env['ir.model.fields']._get(
                'res.partner', 'create_date').id,
        })
        self._share(dashboard, user_id=self.viewer.id)
        copy = dashboard.copy()
        self.assertEqual(copy.user_id, self.env.user)
        self.assertEqual(copy.visibility, 'private')
        self.assertEqual(copy.dashboard_type, 'dynamic')
        self.assertFalse(copy.is_default)
        self.assertFalse(copy.is_favorite)
        self.assertFalse(copy.access_ids)
        self.assertEqual(len(copy.widget_ids), 1)
        self.assertEqual(len(copy.filter_ids), 1)
        self.assertTrue(copy.name.startswith(dashboard.name))

    def test_set_default_and_favorite(self):
        first = self._create_dashboard(user_id=self.editor.id, is_default=True)
        second = self._create_dashboard(user_id=self.editor.id)
        second.with_user(self.editor).action_set_default()
        self.assertTrue(second.is_default)
        self.assertFalse(first.is_default)
        second.with_user(self.editor).action_toggle_favorite()
        self.assertTrue(second.is_favorite)

    def test_layout_persistence(self):
        dashboard = self._create_dashboard()
        widget = self._create_widget(dashboard)
        dashboard.write({'layout_config': {'columns': 12}})
        widget.write({'position_x': 3, 'position_y': 1, 'width': 6, 'height': 2})
        self.assertEqual(dashboard.layout_config, {'columns': 12})
        self.assertEqual(widget.position_x, 3)
        self.assertEqual(widget.width, 6)

    def test_editor_creates_own_dashboard_only(self):
        dashboard = self.env['dashboard.suite'].with_user(self.editor).create({
            'name': 'Personal',
        })
        self.assertEqual(dashboard.user_id, self.editor)
        with self.assertRaises(AccessError):
            self.env['dashboard.suite'].with_user(self.editor).create({
                'name': 'For someone else',
                'user_id': self.viewer.id,
            })
        with self.assertRaises(AccessError):
            self.env['dashboard.suite'].with_user(self.editor).create({
                'name': 'Template',
                'dashboard_type': 'predefined',
            })

    # ------------------------------------------------------------------
    # Sharing and access levels
    # ------------------------------------------------------------------
    def test_viewer_read_only(self):
        dashboard = self._create_dashboard(user_id=self.editor.id)
        self._share(dashboard, user_id=self.viewer.id, access_level='viewer')
        self.assertEqual(
            dashboard.with_user(self.viewer).read(['name'])[0]['name'],
            dashboard.name)
        with self.assertRaises(AccessError):
            dashboard.with_user(self.viewer).write({'description': 'x'})
        with self.assertRaises(AccessError):
            dashboard.with_user(self.viewer).unlink()

    def test_editor_can_edit_but_not_share(self):
        dashboard = self._create_dashboard(user_id=self.viewer.id)
        self._share(dashboard, user_id=self.editor.id, access_level='editor')
        dashboard.with_user(self.editor).write({'description': 'edited'})
        self.assertEqual(dashboard.description, 'edited')
        self._create_widget(dashboard)
        with self.assertRaises(AccessError):
            dashboard.with_user(self.editor).write({'visibility': 'shared'})
        with self.assertRaises(AccessError):
            dashboard.with_user(self.editor).write({
                'access_ids': [(0, 0, {'user_id': self.manager.id})],
            })

    def test_shared_viewer_can_favorite(self):
        dashboard = self._create_dashboard(user_id=self.editor.id)
        self._share(dashboard, user_id=self.viewer.id, access_level='viewer')
        dashboard.with_user(self.viewer).action_toggle_favorite()
        self.assertTrue(dashboard.is_favorite)

    def test_manager_sees_and_edits_everything(self):
        dashboard = self._create_dashboard(user_id=self.editor.id)
        self.assertIn(dashboard.id, self.env['dashboard.suite'].with_user(
            self.manager).search([]).ids)
        dashboard.with_user(self.manager).write({'description': 'managed'})
        self.assertEqual(dashboard.description, 'managed')
        dashboard.with_user(self.manager).unlink()
        self.assertFalse(dashboard.exists())

    def test_outsider_has_no_access(self):
        dashboard = self._create_dashboard(user_id=self.editor.id)
        with self.assertRaises(AccessError):
            dashboard.with_user(self.outsider).read(['name'])
        with self.assertRaises(AccessError):
            self.env['dashboard.suite'].with_user(self.outsider).search([])

    def test_predefined_is_read_only_for_users(self):
        dashboard = self._create_dashboard(
            dashboard_type='predefined', user_id=self.manager.id)
        self._share(dashboard, user_id=self.editor.id, access_level='editor')
        with self.assertRaises(AccessError):
            dashboard.with_user(self.editor).write({'description': 'edit'})
        copy = dashboard.with_user(self.editor).action_duplicate()
        new_dashboard = self.env['dashboard.suite'].browse(copy['res_id'])
        self.assertEqual(new_dashboard.dashboard_type, 'dynamic')
        self.assertEqual(new_dashboard.user_id, self.editor)
        self.assertTrue(new_dashboard.visibility == 'private')

    def test_company_scope(self):
        dashboard = self._create_dashboard(
            user_id=self.company_2_user.id,
            company_ids=[(6, 0, [self.company_2.id])])
        self.assertIn(dashboard.id, self.env['dashboard.suite'].with_user(
            self.company_2_user).search([]).ids)
        self.assertNotIn(dashboard.id, self.env['dashboard.suite'].with_user(
            self.editor).search([]).ids)

    def test_sharing_validation(self):
        dashboard = self._create_dashboard(user_id=self.editor.id)
        with self.assertRaises(ValidationError):
            self._share(dashboard)
        with self.assertRaises(ValidationError):
            self._share(
                dashboard, user_id=self.viewer.id,
                group_id=self.env.ref(GROUP_VIEWER).id)
        self._share(dashboard, user_id=self.viewer.id)
        with self.assertRaises(ValidationError):
            self._share(dashboard, user_id=self.viewer.id)

    # ------------------------------------------------------------------
    # Widget and filter configuration
    # ------------------------------------------------------------------
    def test_widget_rejects_foreign_model_field(self):
        dashboard = self._create_dashboard()
        other_field = self.env['ir.model.fields']._get('res.company', 'id')
        with self.assertRaises(ValidationError):
            self._create_widget(
                dashboard, operation='sum', measure_field_id=other_field.id)

    def test_widget_rejects_non_numeric_measure(self):
        dashboard = self._create_dashboard()
        country = self.env['ir.model.fields']._get('res.partner', 'country_id')
        with self.assertRaises(ValidationError):
            self._create_widget(
                dashboard, operation='sum', measure_field_id=country.id)

    def test_widget_rejects_non_stored_measure(self):
        dashboard = self._create_dashboard()
        display_name = self.env['ir.model.fields']._get(
            'res.partner', 'display_name')
        self.assertFalse(display_name.store)
        with self.assertRaises(ValidationError):
            self._create_widget(
                dashboard, operation='sum', measure_field_id=display_name.id)

    def test_widget_requires_measure_for_aggregation(self):
        dashboard = self._create_dashboard()
        with self.assertRaises(ValidationError):
            self._create_widget(dashboard, operation='sum')

    def test_chart_requires_group_by(self):
        dashboard = self._create_dashboard()
        with self.assertRaises(ValidationError):
            self._create_widget(dashboard, widget_type='chart', chart_type='bar')
        group_field = self.env['ir.model.fields']._get(
            'res.partner', 'is_company')
        chart = self._create_widget(
            dashboard, widget_type='chart', chart_type='bar',
            group_by_field_id=group_field.id)
        self.assertEqual(chart.chart_type, 'bar')

    def test_domain_validation(self):
        dashboard = self._create_dashboard()
        with self.assertRaises(ValidationError):
            self._create_widget(dashboard, domain='[(')
        with self.assertRaises(ValidationError):
            self._create_widget(dashboard, domain=[['unknown_field', '=', 1]])
        with self.assertRaises(ValidationError):
            self._create_widget(dashboard, domain=[['name', 'sql', 'x']])
        widget = self._create_widget(
            dashboard,
            domain=[['is_company', '=', True], ['country_id', '!=', False]])
        self.assertEqual(len(widget.domain), 2)

    def test_widget_limits(self):
        dashboard = self._create_dashboard()
        with self.assertRaises(ValidationError):
            self._create_widget(dashboard, limit=0)
        with self.assertRaises(ValidationError):
            self._create_widget(dashboard, limit=501)
        with self.assertRaises(ValidationError):
            self._create_widget(dashboard, width=13)

    def test_widget_config_validation(self):
        dashboard = self._create_dashboard()
        with self.assertRaises(ValidationError):
            self._create_widget(
                dashboard, widget_type='table',
                config={'columns': ['nope']})
        with self.assertRaises(ValidationError):
            self._create_widget(
                dashboard, widget_type='progress', config={'target': -5})
        widget = self._create_widget(
            dashboard, widget_type='progress', config={'target': 100})
        self.assertEqual(widget.config, {'target': 100})

    def test_filter_validation(self):
        dashboard = self._create_dashboard()
        name_field = self.env['ir.model.fields']._get('res.partner', 'name')
        date_field = self.env['ir.model.fields']._get(
            'res.partner', 'create_date')
        with self.assertRaises(ValidationError):
            self.env['dashboard.suite.filter'].create({
                'name': 'Bad date filter',
                'dashboard_id': dashboard.id,
                'filter_type': 'date',
                'field_id': name_field.id,
            })
        dashboard_filter = self.env['dashboard.suite.filter'].create({
            'name': 'Created',
            'dashboard_id': dashboard.id,
            'filter_type': 'date',
            'field_id': date_field.id,
            'operator': '>=',
        })
        self.assertEqual(dashboard_filter.filter_type, 'date')
        with self.assertRaises(ValidationError):
            self.env['dashboard.suite.filter'].create({
                'name': 'No field',
                'dashboard_id': dashboard.id,
                'filter_type': 'selection',
            })
