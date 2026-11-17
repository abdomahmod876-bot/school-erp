from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestSchoolTeacher(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Teacher Test School',
            'code': 'TTS',
        })
        cls.subject = cls.env['school.subject'].create({
            'name': 'Mathematics',
            'code': 'MATH',
            'school_id': cls.school.id,
        })
        cls.teacher = cls.env['school.teacher'].create({
            'name': 'Salma Fathy',
            'gender': 'female',
            'school_id': cls.school.id,
            'subject_ids': [(6, 0, [cls.subject.id])],
        })

    def test_reference_is_generated(self):
        self.assertTrue(self.teacher.reference.startswith('TCH/'))

    def test_subject_must_belong_to_teacher_school(self):
        other_school = self.env['school.school'].create({
            'name': 'Other School',
            'code': 'OTS',
        })
        other_subject = self.env['school.subject'].create({
            'name': 'Physics',
            'school_id': other_school.id,
        })
        with self.assertRaises(ValidationError):
            self.teacher.write({'subject_ids': [(4, other_subject.id)]})

    def test_state_actions(self):
        self.assertEqual(self.teacher.state, 'active')
        self.teacher.action_set_on_leave()
        self.assertEqual(self.teacher.state, 'on_leave')
        self.teacher.action_set_active()
        self.assertEqual(self.teacher.state, 'active')
        self.teacher.action_terminate()
        self.assertEqual(self.teacher.state, 'terminated')

    def test_contract_type_options(self):
        for contract_type in ('full_time', 'part_time', 'hourly'):
            self.teacher.contract_type = contract_type
            self.assertEqual(self.teacher.contract_type, contract_type)

    def test_age_is_computed_from_birth_date(self):
        self.teacher.birth_date = '1990-06-15'
        self.assertEqual(self.teacher.age, 36)

    def test_user_account_is_unique(self):
        user = self.env['res.users'].create({
            'name': 'Teacher Login',
            'login': 'school_teacher_login',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        self.teacher.user_id = user
        other = self.env['school.teacher'].create({
            'name': 'Second Teacher',
            'gender': 'male',
            'school_id': self.school.id,
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                other.user_id = user
                self.env.flush_all()
