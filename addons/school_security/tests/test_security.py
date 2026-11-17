from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchoolSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Security Test School',
            'code': 'STS',
        })
        cls.other_school = cls.env['school.school'].create({
            'name': 'Security Other School',
            'code': 'SOS',
        })
        cls.branch = cls.env['school.branch'].create({
            'name': 'Main Branch',
            'code': 'MAIN',
            'school_id': cls.school.id,
        })
        internal_group = cls.env.ref('base.group_user')
        cls.user = cls.env['res.users'].create({
            'name': 'Access User',
            'login': 'school_access_user',
            'group_ids': [Command.set([internal_group.id])],
        })
        cls.other_user = cls.env['res.users'].create({
            'name': 'Second Access User',
            'login': 'school_access_user_2',
            'group_ids': [Command.set([internal_group.id])],
        })
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Access Portal User',
            'login': 'school_access_portal',
            'group_ids': [Command.set([cls.env.ref('base.group_portal').id])],
        })

    def _wizard(self, users, **values):
        values.setdefault('action', 'grant')
        return self.env['school.access.wizard'].create({
            'user_ids': [Command.set(users.ids)],
            **values,
        })

    def _logs(self, action=None):
        domain = [('user_id', 'in', (self.user | self.other_user).ids)]
        if action:
            domain.append(('action', '=', action))
        return self.env['school.access.log'].search(domain)

    def test_grant_school_and_branch(self):
        wizard = self._wizard(
            self.user,
            school_ids=[Command.set([self.school.id])],
            branch_ids=[Command.set([self.branch.id])],
        )
        action = wizard.action_apply()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertIn(self.school, self.user.school_ids)
        self.assertIn(self.branch, self.user.branch_ids)
        self.assertEqual(self.user.default_school_id, self.school)

        log = self._logs('grant')
        self.assertEqual(len(log), 1)
        self.assertEqual(log.user_id, self.user)
        self.assertEqual(log.school_id, self.school)
        self.assertEqual(log.granted_by, self.env.user)
        self.assertIn(self.branch.display_name, log.note)

    def test_grant_branch_implies_school(self):
        wizard = self._wizard(
            self.user,
            branch_ids=[Command.set([self.branch.id])],
        )
        wizard.action_apply()
        self.assertIn(self.school, self.user.school_ids)
        self.assertIn(self.branch, self.user.branch_ids)

    def test_grant_multiple_users_and_schools(self):
        wizard = self._wizard(
            self.user | self.other_user,
            school_ids=[Command.set([self.school.id, self.other_school.id])],
        )
        wizard.action_apply()
        for user in (self.user, self.other_user):
            self.assertEqual(user.school_ids, self.school | self.other_school)
            self.assertEqual(user.default_school_id, self.school)
        self.assertEqual(len(self._logs('grant')), 4)

    def test_revoke_clears_access(self):
        self._wizard(
            self.user,
            school_ids=[Command.set([self.school.id])],
            branch_ids=[Command.set([self.branch.id])],
        ).action_apply()
        self.assertTrue(self.user.school_ids)

        revoke = self._wizard(
            self.user,
            school_ids=[Command.set([self.school.id])],
            branch_ids=[Command.set([self.branch.id])],
            action='revoke',
        )
        revoke.action_apply()
        self.assertNotIn(self.school, self.user.school_ids)
        self.assertNotIn(self.branch, self.user.branch_ids)
        self.assertFalse(self.user.default_school_id)
        self.assertEqual(len(self._logs('revoke')), 1)

    def test_identical_grant_is_idempotent(self):
        self._wizard(
            self.user, school_ids=[Command.set([self.school.id])],
        ).action_apply()
        self._wizard(
            self.user, school_ids=[Command.set([self.school.id])],
        ).action_apply()
        self.assertEqual(self.user.school_ids, self.school)
        self.assertEqual(len(self._logs('grant')), 2)

    def test_portal_user_is_rejected(self):
        wizard = self._wizard(
            self.portal_user, school_ids=[Command.set([self.school.id])],
        )
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_missing_target_is_rejected(self):
        with self.assertRaises(UserError):
            self._wizard(self.user).action_apply()

    def test_log_display_name(self):
        log = self.env['school.access.log'].create({
            'user_id': self.user.id,
            'school_id': self.school.id,
            'action': 'revoke',
        })
        self.assertEqual(
            log.display_name,
            'Revoked - Security Test School / Access User',
        )
