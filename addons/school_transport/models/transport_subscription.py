from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolTransportSubscription(models.Model):
    _name = 'school.transport.subscription'
    _inherit = ['school.mixin', 'mail.thread']
    _description = 'Transport Subscription'
    _order = 'date_start desc, id desc'

    reference = fields.Char(
        string='Subscription No.', default='New', copy=False,
        readonly=True, index=True, tracking=True)
    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    route_id = fields.Many2one(
        'school.transport.route', string='Route', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    stop_id = fields.Many2one(
        'school.transport.stop', string='Stop', ondelete='restrict',
        domain="[('route_id', '=', route_id)]")
    direction = fields.Selection(
        selection=[
            ('both', 'Pickup and Drop-off'),
            ('pickup', 'Pickup Only'),
            ('dropoff', 'Drop-off Only'),
        ],
        required=True, default='both')
    date_start = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date()
    monthly_fee = fields.Float(digits=(16, 2))
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('running', 'Running'),
            ('cancelled', 'Cancelled'),
        ],
        required=True, default='draft', tracking=True, index=True)
    note = fields.Text()

    _reference_uniq = models.Constraint(
        'UNIQUE(reference)',
        'The subscription number must be unique.',
    )

    @api.constrains('student_id', 'school_id')
    def _check_student_school(self):
        for subscription in self:
            if subscription.student_id.school_id != subscription.school_id:
                raise ValidationError(
                    _('The student does not belong to the selected school.'))

    @api.constrains('stop_id', 'route_id')
    def _check_stop_route(self):
        for subscription in self:
            if subscription.stop_id and subscription.stop_id.route_id != subscription.route_id:
                raise ValidationError(_(
                    'The stop %(stop)s does not belong to the route %(route)s.',
                    stop=subscription.stop_id.name,
                    route=subscription.route_id.name))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for subscription in self:
            if subscription.date_end and subscription.date_end < subscription.date_start:
                raise ValidationError(_(
                    'The end date must be on or after the start date.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code(
                        'school.transport.subscription')
                    or 'New')
        return super().create(vals_list)

    def action_confirm(self):
        for subscription in self:
            if subscription.state != 'draft':
                raise UserError(
                    _('Only draft subscriptions can be confirmed.'))
            route = subscription.route_id
            vehicle = route.vehicle_id
            if not vehicle:
                raise UserError(_(
                    'Assign a vehicle to the route %(route)s before confirming '
                    'subscriptions.', route=route.name))
            running = len(route.subscription_ids.filtered(
                lambda other: other.state == 'running'))
            if running >= vehicle.capacity:
                raise UserError(_(
                    'The vehicle %(vehicle)s is full: %(capacity)s seats are '
                    'already taken on %(route)s.',
                    vehicle=vehicle.name,
                    capacity=vehicle.capacity,
                    route=route.name))
        self.write({'state': 'running'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    transport_subscription_ids = fields.One2many(
        'school.transport.subscription', 'student_id',
        string='Transport Subscriptions')
