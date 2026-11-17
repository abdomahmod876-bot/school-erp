from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSchoolCommunication(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Communication Test School',
            'code': 'CTS',
        })
        cls.guardian_partner = cls.env['res.partner'].create({
            'name': 'Hany Ibrahim',
            'email': 'hany@example.com',
        })
        cls.other_partner = cls.env['res.partner'].create({
            'name': 'No Email Guardian',
        })
        cls.student = cls.env['school.student'].create({
            'name': 'Omar Hany',
            'gender': 'male',
            'school_id': cls.school.id,
            'state': 'active',
        })
        cls.env['school.student.guardian'].create({
            'student_id': cls.student.id,
            'partner_id': cls.guardian_partner.id,
            'is_primary': True,
        })
        cls.announcement = cls.env['school.announcement'].create({
            'name': 'Second Term Schedule',
            'body': '<p>The second term starts next Sunday.</p>',
            'audience': 'guardians',
            'school_id': cls.school.id,
        })

    def _publish(self):
        self.announcement.action_publish()
        return self.announcement

    def test_publish_posts_to_chatter(self):
        announcement = self._publish()
        self.assertEqual(announcement.state, 'published')
        self.assertTrue(announcement.message_ids)

    def test_notify_requires_published_announcement(self):
        with self.assertRaises(UserError):
            self.announcement.action_notify_guardians()

    def test_notify_creates_one_message_per_guardian(self):
        announcement = self._publish()
        announcement.action_notify_guardians()
        self.assertEqual(len(announcement.notification_ids), 1)
        message = announcement.notification_ids
        self.assertEqual(message.partner_id, self.guardian_partner)
        self.assertNotEqual(message.reference, 'New')
        self.assertEqual(message.subject, announcement.name)
        self.assertEqual(message.school_id, self.school)

    def test_notify_twice_raises(self):
        announcement = self._publish()
        announcement.action_notify_guardians()
        with self.assertRaises(UserError):
            announcement.action_notify_guardians()

    def test_notification_duplicate_recipient_is_rejected(self):
        announcement = self._publish()
        announcement.action_notify_guardians()
        with self.assertRaises(ValidationError):
            self.env['school.communication.message'].create({
                'announcement_id': announcement.id,
                'partner_id': self.guardian_partner.id,
                'channel': 'portal',
                'subject': announcement.name,
            })

    def test_portal_send_requires_published_announcement(self):
        message = self.env['school.communication.message'].create({
            'announcement_id': self.announcement.id,
            'partner_id': self.guardian_partner.id,
            'channel': 'portal',
            'subject': self.announcement.name,
        })
        with self.assertRaises(UserError):
            message.action_send()

    def test_portal_send_marks_message_sent(self):
        announcement = self._publish()
        message = self.env['school.communication.message'].create({
            'announcement_id': announcement.id,
            'partner_id': self.guardian_partner.id,
            'channel': 'portal',
            'subject': announcement.name,
        })
        message.action_send()
        self.assertEqual(message.state, 'sent')
        self.assertTrue(message.sent_date)
        self.assertEqual(announcement.sent_count, 1)

    def test_email_send_requires_address(self):
        announcement = self._publish()
        message = self.env['school.communication.message'].create({
            'announcement_id': announcement.id,
            'partner_id': self.other_partner.id,
            'channel': 'email',
            'subject': announcement.name,
        })
        with self.assertRaises(UserError):
            message.action_send()

    def test_reset_draft_blocked_after_sent(self):
        announcement = self._publish()
        announcement.action_notify_guardians()
        message = announcement.notification_ids
        message.action_send()
        with self.assertRaises(UserError):
            announcement.action_reset_draft()

    def test_reset_draft_clears_unsent_notifications(self):
        announcement = self._publish()
        announcement.action_notify_guardians()
        announcement.action_reset_draft()
        self.assertEqual(announcement.state, 'draft')
        self.assertFalse(announcement.notification_ids)
