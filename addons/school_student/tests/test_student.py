from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestSchoolStudent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Student Test School',
            'code': 'STS',
        })
        cls.student = cls.env['school.student'].create({
            'name': 'Omar Hassan',
            'gender': 'male',
            'school_id': cls.school.id,
        })

    def test_reference_is_generated(self):
        self.assertTrue(self.student.reference.startswith('STU/'))

    def test_only_one_primary_guardian(self):
        father = self.env['res.partner'].create({'name': 'Hassan Ali'})
        mother = self.env['res.partner'].create({'name': 'Mona Samir'})
        self.env['school.student.guardian'].create({
            'student_id': self.student.id,
            'partner_id': father.id,
            'relation': 'father',
            'is_primary': True,
        })
        self.assertTrue(father.is_school_guardian)
        self.assertEqual(self.student.primary_guardian_id, father)
        with self.assertRaises(ValidationError):
            self.env['school.student.guardian'].create({
                'student_id': self.student.id,
                'partner_id': mother.id,
                'relation': 'mother',
                'is_primary': True,
            })

    def test_state_actions(self):
        self.assertEqual(self.student.state, 'active')
        self.student.action_withdraw()
        self.assertEqual(self.student.state, 'withdrawn')
        self.student.action_activate()
        self.assertEqual(self.student.state, 'active')
        self.student.action_graduate()
        self.assertEqual(self.student.state, 'graduated')

    def test_blood_group_options(self):
        for blood_group in ('a+', 'a-', 'b+', 'b-', 'ab+', 'ab-', 'o+', 'o-'):
            self.student.blood_group = blood_group
            self.assertEqual(self.student.blood_group, blood_group)

    def test_age_is_computed_from_birth_date(self):
        self.student.birth_date = '2016-01-01'
        self.assertEqual(self.student.age, 10)

    def test_reference_is_unique(self):
        other = self.env['school.student'].create({
            'name': 'Second Student',
            'gender': 'female',
            'school_id': self.school.id,
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                other.reference = self.student.reference
                self.env.flush_all()
