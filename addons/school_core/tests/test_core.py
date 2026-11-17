from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestSchoolCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Core Test School',
            'code': 'CTS',
        })
        cls.other_school = cls.env['school.school'].create({
            'name': 'Other Core School',
            'code': 'OCS',
        })
        cls.branch = cls.env['school.branch'].create({
            'name': 'Main Branch',
            'code': 'MAIN',
            'school_id': cls.school.id,
        })
        cls.other_branch = cls.env['school.branch'].create({
            'name': 'Other Branch',
            'code': 'MAIN',
            'school_id': cls.other_school.id,
        })

    def _create_user(self, login, **values):
        values.setdefault('name', login)
        values.setdefault('login', login)
        return self.env['res.users'].create(values)

    def test_school_defaults_and_grading_systems(self):
        self.assertEqual(self.school.grading_system, 'percentage')
        self.assertAlmostEqual(self.school.pass_mark, 50.0)
        self.assertEqual(self.school.branch_count, 1)
        for grading_system in ('percentage', 'points', 'letters'):
            self.school.grading_system = grading_system
            self.assertEqual(self.school.grading_system, grading_system)

    def test_action_open_branches(self):
        action = self.school.action_open_branches()
        self.assertEqual(action['res_model'], 'school.branch')
        self.assertEqual(action['domain'], [('school_id', '=', self.school.id)])
        self.assertEqual(action['context']['default_school_id'], self.school.id)

    def test_branch_display_name(self):
        self.assertEqual(self.branch.display_name, 'Core Test School / Main Branch')

    def test_branch_code_unique_per_school(self):
        # The same code is already used by other_branch in another school.
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.branch'].create({
                    'name': 'Duplicate Branch',
                    'code': 'MAIN',
                    'school_id': self.school.id,
                })
                self.env.flush_all()

    def test_school_code_unique_per_company(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['school.school'].create({
                    'name': 'Duplicate Code School',
                    'code': 'CTS',
                })
                self.env.flush_all()

    def test_school_code_generated_from_name(self):
        school = self.env['school.school'].create({'name': 'Cairo Modern School'})
        self.assertEqual(school.code, 'CMS')
        single_word = self.env['school.school'].create({'name': 'Alphabet'})
        self.assertEqual(single_word.code, 'ALPH')

    def test_generated_school_code_is_unique(self):
        first = self.env['school.school'].create({'name': 'Green Valley School'})
        second = self.env['school.school'].create({'name': 'Green Valley School'})
        self.assertEqual(first.code, 'GVS')
        self.assertEqual(second.code, 'GVS2')

    def test_manual_school_code_is_kept(self):
        school = self.env['school.school'].create({
            'name': 'Manual Code School',
            'code': 'MCS',
        })
        self.assertEqual(school.code, 'MCS')

    def test_clearing_code_regenerates_it(self):
        school = self.env['school.school'].create({'name': 'Regenerate Code School'})
        self.assertEqual(school.code, 'RCS')
        school.code = False
        self.assertEqual(school.code, 'RCS')

    def test_school_code_onchange_from_name(self):
        school = self.env['school.school'].new({'name': 'Sunrise International School'})
        school._onchange_name_generate_code()
        self.assertEqual(school.code, 'SIS')

    def test_mixin_rejects_branch_of_another_school(self):
        with self.assertRaises(ValidationError):
            self.env['school.student'].create({
                'name': 'Wrong Branch Student',
                'gender': 'male',
                'school_id': self.school.id,
                'branch_id': self.other_branch.id,
            })

    def test_user_can_manage_default_branch(self):
        user = self.env['res.users'].new({
            'name': 'Onchange User',
            'login': 'core_onchange_user',
        })
        user.default_branch_id = self.branch
        user._onchange_default_branch_id()
        self.assertEqual(user.default_school_id, self.school)
        self.assertIn(self.school, user.school_ids._origin)
        self.assertIn(self.branch, user.branch_ids._origin)

        user.default_school_id = self.other_school
        user._onchange_default_school_id()
        self.assertIn(self.other_school, user.school_ids._origin)
        self.assertFalse(user.default_branch_id)

    def test_user_branch_requires_school(self):
        with self.assertRaises(ValidationError):
            self._create_user(
                'core_branch_only_user',
                branch_ids=[Command.set([self.branch.id])],
            )

    def test_user_branch_must_belong_to_allowed_schools(self):
        with self.assertRaises(ValidationError):
            self._create_user(
                'core_mixed_scope_user',
                school_ids=[Command.set([self.school.id])],
                branch_ids=[Command.set([self.other_branch.id])],
            )

    def test_user_default_school_must_be_allowed(self):
        with self.assertRaises(ValidationError):
            self._create_user(
                'core_default_school_user',
                school_ids=[Command.set([self.school.id])],
                default_school_id=self.other_school.id,
            )

    def test_user_default_branch_must_be_allowed(self):
        with self.assertRaises(ValidationError):
            self._create_user(
                'core_default_branch_user',
                school_ids=[Command.set([self.school.id, self.other_school.id])],
                branch_ids=[Command.set([self.branch.id])],
                default_branch_id=self.other_branch.id,
            )

    def test_school_record_rule_limits_visible_schools(self):
        teacher_group = self.env.ref('school_core.group_school_teacher')
        user = self._create_user(
            'core_scoped_teacher',
            group_ids=[Command.set([teacher_group.id])],
            school_ids=[Command.set([self.school.id])],
        )
        visible_schools = self.env['school.school'].with_user(user).search([])
        self.assertEqual(visible_schools, self.school)
        visible_branches = self.env['school.branch'].with_user(user).search([])
        self.assertEqual(visible_branches, self.branch)
