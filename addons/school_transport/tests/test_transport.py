from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSchoolTransport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Transport Test School',
            'code': 'TTS',
        })
        cls.vehicle = cls.env['school.transport.vehicle'].create({
            'name': 'Bus 1',
            'plate_number': 'TRN-0001',
            'capacity': 1,
            'school_id': cls.school.id,
        })
        cls.route = cls.env['school.transport.route'].create({
            'name': 'Nasr City',
            'code': 'NC-01',
            'school_id': cls.school.id,
            'vehicle_id': cls.vehicle.id,
            'stop_ids': [
                (0, 0, {'name': 'Stop A', 'sequence': 10}),
                (0, 0, {'name': 'Stop B', 'sequence': 20}),
            ],
        })
        cls.stop_a = cls.route.stop_ids.filtered(lambda stop: stop.name == 'Stop A')
        cls.stop_b = cls.route.stop_ids.filtered(lambda stop: stop.name == 'Stop B')
        cls.students = cls.env['school.student'].create([
            {'name': 'Student One', 'gender': 'male', 'school_id': cls.school.id},
            {'name': 'Student Two', 'gender': 'female', 'school_id': cls.school.id},
        ])

    def _subscription(self, student, **kwargs):
        values = {
            'school_id': self.school.id,
            'student_id': student.id,
            'route_id': self.route.id,
            'stop_id': self.stop_a.id,
        }
        values.update(kwargs)
        return self.env['school.transport.subscription'].create(values)

    def test_subscription_flow(self):
        subscription = self._subscription(self.students[0])
        self.assertEqual(subscription.state, 'draft')
        self.assertNotEqual(subscription.reference, 'New')
        subscription.action_confirm()
        self.assertEqual(subscription.state, 'running')
        self.assertEqual(self.route.running_count, 1)

    def test_capacity_is_enforced(self):
        first = self._subscription(self.students[0])
        first.action_confirm()
        second = self._subscription(self.students[1])
        with self.assertRaises(UserError):
            second.action_confirm()

    def test_cancel_releases_a_seat(self):
        first = self._subscription(self.students[0])
        first.action_confirm()
        first.action_cancel()
        self.assertEqual(first.state, 'cancelled')
        second = self._subscription(self.students[1])
        second.action_confirm()
        self.assertEqual(second.state, 'running')

    def test_confirm_requires_vehicle(self):
        route = self.env['school.transport.route'].create({
            'name': 'No Vehicle Route',
            'school_id': self.school.id,
        })
        subscription = self._subscription(self.students[0], route_id=route.id, stop_id=False)
        with self.assertRaises(UserError):
            subscription.action_confirm()

    def test_direction_options(self):
        for direction in ('both', 'pickup', 'dropoff'):
            subscription = self._subscription(self.students[0], direction=direction)
            self.assertEqual(subscription.direction, direction)

    def test_reset_draft_cycle(self):
        subscription = self._subscription(self.students[0])
        subscription.action_confirm()
        self.assertEqual(subscription.state, 'running')
        subscription.action_reset_draft()
        self.assertEqual(subscription.state, 'draft')
        subscription.action_confirm()
        subscription.action_cancel()
        self.assertEqual(subscription.state, 'cancelled')
        subscription.action_reset_draft()
        subscription.action_confirm()
        self.assertEqual(subscription.state, 'running')

    def test_stop_must_belong_to_route(self):
        other_route = self.env['school.transport.route'].create({
            'name': 'Other Route',
            'school_id': self.school.id,
            'stop_ids': [(0, 0, {'name': 'Other Stop', 'sequence': 10})],
        })
        with self.assertRaises(ValidationError):
            self._subscription(
                self.students[0],
                stop_id=other_route.stop_ids.id,
            )

    def test_date_range(self):
        with self.assertRaises(ValidationError):
            self._subscription(
                self.students[0],
                date_start='2026-10-10',
                date_end='2026-10-01',
            )

    def test_stop_must_belong_to_route(self):
        other_route = self.env['school.transport.route'].create({
            'name': 'Other Route',
            'school_id': self.school.id,
            'stop_ids': [(0, 0, {'name': 'Other Stop'})],
        })
        other_stop = other_route.stop_ids[:1]
        with self.assertRaises(ValidationError):
            self._subscription(self.students[0], stop_id=other_stop.id)

    def test_dates_are_checked(self):
        with self.assertRaises(ValidationError):
            self._subscription(
                self.students[0],
                date_end='2020-01-01',
            )
