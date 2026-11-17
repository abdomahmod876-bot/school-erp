from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolAnnouncement(models.Model):
    _name = 'school.announcement'
    _inherit = ['school.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'School Announcement'
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True, tracking=True)
    body = fields.Html(required=True)
    audience = fields.Selection(
        selection=[
            ('all', 'Everyone'),
            ('guardians', 'Guardians'),
            ('students', 'Students'),
            ('teachers', 'Teachers'),
        ],
        required=True, default='all', tracking=True)
    date_start = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date()
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('cancelled', 'Cancelled'),
        ],
        required=True, default='draft', tracking=True, index=True)
    published_date = fields.Date(readonly=True)
    notify_guardians = fields.Boolean(
        help='Create one message per guardian when notifying.')
    notification_channel = fields.Selection(
        selection=[
            ('portal', 'Portal'),
            ('email', 'Email'),
        ],
        required=True, default='portal')
    notification_ids = fields.One2many(
        'school.communication.message', 'announcement_id',
        string='Notifications')
    notification_count = fields.Integer(compute='_compute_notification_stats')
    sent_count = fields.Integer(compute='_compute_notification_stats')

    @api.depends('notification_ids.state')
    def _compute_notification_stats(self):
        for announcement in self:
            notifications = announcement.notification_ids
            announcement.notification_count = len(notifications)
            announcement.sent_count = len(notifications.filtered(
                lambda message: message.state == 'sent'))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for announcement in self:
            if announcement.date_end and announcement.date_end < announcement.date_start:
                raise ValidationError(_(
                    'The end date must be on or after the start date.'))

    def action_publish(self):
        for announcement in self:
            if announcement.state != 'draft':
                raise UserError(_('Only draft announcements can be published.'))
            if not announcement.body:
                raise UserError(_('Write the announcement body before publishing.'))
        self.write({
            'state': 'published',
            'published_date': fields.Date.context_today(self),
        })
        for announcement in self:
            announcement.message_post(body=announcement.body)

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for announcement in self:
            if announcement.notification_ids.filtered(
                    lambda message: message.state == 'sent'):
                raise UserError(_(
                    'Announcements with sent notifications cannot be reset to draft.'))
        self.write({
            'state': 'draft',
            'published_date': False,
            'notification_ids': [(5, 0, 0)],
        })

    def _get_guardian_partners(self):
        self.ensure_one()
        students = self.env['school.student'].search([
            ('school_id', '=', self.school_id.id),
            ('active', '=', True),
            ('state', 'in', ('active', 'graduated')),
        ])
        return students.guardian_ids.partner_id

    def action_notify_guardians(self):
        for announcement in self:
            if announcement.state != 'published':
                raise UserError(_(
                    'Publish the announcement before notifying guardians.'))
            partners = announcement._get_guardian_partners()
            if not partners:
                raise UserError(_(
                    'There is no guardian linked to the students of this school.'))
            already_notified = announcement.notification_ids.partner_id
            missing = partners - already_notified
            if not missing:
                raise UserError(_('Every guardian is already notified.'))
            announcement.write({
                'notification_ids': [(0, 0, {
                    'partner_id': partner.id,
                    'channel': announcement.notification_channel,
                    'subject': announcement.name,
                    'body': announcement.body,
                }) for partner in missing],
            })
