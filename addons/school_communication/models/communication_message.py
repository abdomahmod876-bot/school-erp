from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolCommunicationMessage(models.Model):
    _name = 'school.communication.message'
    _description = 'Communication Message'
    _order = 'create_date desc, id desc'

    reference = fields.Char(
        string='Message No.', default='New', copy=False,
        readonly=True, index=True)
    announcement_id = fields.Many2one(
        'school.announcement', string='Announcement',
        ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Recipient', required=True,
        ondelete='restrict', index=True)
    school_id = fields.Many2one(
        'school.school', related='announcement_id.school_id',
        store=True, readonly=True, index=True)
    channel = fields.Selection(
        selection=[
            ('portal', 'Portal'),
            ('email', 'Email'),
        ],
        required=True, default='portal')
    subject = fields.Char(required=True)
    body = fields.Html()
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
        ],
        required=True, default='draft', index=True)
    sent_date = fields.Date(readonly=True)
    error_message = fields.Char(readonly=True)

    _reference_uniq = models.Constraint(
        'UNIQUE(reference)',
        'The message number must be unique.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code(
                        'school.communication.message')
                    or 'New')
        return super().create(vals_list)

    @api.constrains('announcement_id', 'partner_id')
    def _check_unique_recipient(self):
        for message in self.filtered('announcement_id'):
            duplicates = message.announcement_id.notification_ids.filtered(
                lambda other: other.partner_id == message.partner_id and other != message)
            if duplicates:
                raise ValidationError(_(
                    'The recipient %(partner)s already has a message for this '
                    'announcement.', partner=message.partner_id.display_name))

    def action_send(self):
        for message in self:
            if message.state == 'sent':
                raise UserError(_('The message %s is already sent.', message.reference))
            if message.channel == 'email':
                message._send_email()
            else:
                message._send_portal()
        return True

    def _send_email(self):
        self.ensure_one()
        if not self.partner_id.email:
            raise UserError(_(
                'The recipient %(partner)s has no email address.',
                partner=self.partner_id.display_name))
        mail = self.env['mail.mail'].create({
            'subject': self.subject,
            'body_html': self.body or self.subject,
            'email_to': self.partner_id.email,
            'email_from': (
                self.env.company.email_formatted
                or self.env.user.email_formatted),
        })
        try:
            mail.send()
        except Exception as error:  # noqa: BLE001 - surfaced on the message
            self.write({
                'state': 'failed',
                'error_message': str(error)[:255],
            })
            return
        self.write({
            'state': 'sent',
            'sent_date': fields.Date.context_today(self),
            'error_message': False,
        })

    def _send_portal(self):
        self.ensure_one()
        if not self.announcement_id:
            raise UserError(_('Portal messages must belong to an announcement.'))
        if self.announcement_id.state != 'published':
            raise UserError(_(
                'The announcement must be published before sending portal messages.'))
        self.write({
            'state': 'sent',
            'sent_date': fields.Date.context_today(self),
        })

    def action_reset_draft(self):
        self.write({
            'state': 'draft',
            'sent_date': False,
            'error_message': False,
        })
