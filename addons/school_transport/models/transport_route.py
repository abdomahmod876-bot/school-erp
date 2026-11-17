from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolTransportRoute(models.Model):
    _name = 'school.transport.route'
    _inherit = ['school.mixin', 'mail.thread']
    _description = 'Transport Route'
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char()
    vehicle_id = fields.Many2one(
        'school.transport.vehicle', string='Vehicle',
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    stop_ids = fields.One2many(
        'school.transport.stop', 'route_id', string='Stops')
    subscription_ids = fields.One2many(
        'school.transport.subscription', 'route_id', string='Subscriptions')
    stop_count = fields.Integer(compute='_compute_stats')
    subscription_count = fields.Integer(compute='_compute_stats')
    running_count = fields.Integer(compute='_compute_stats')
    note = fields.Text()
    active = fields.Boolean(default=True)

    _name_school_uniq = models.Constraint(
        'UNIQUE(name, school_id)',
        'The route name must be unique per school.',
    )

    @api.depends('stop_ids', 'subscription_ids.state')
    def _compute_stats(self):
        for route in self:
            running = route.subscription_ids.filtered(
                lambda subscription: subscription.state == 'running')
            route.stop_count = len(route.stop_ids)
            route.subscription_count = len(route.subscription_ids)
            route.running_count = len(running)

    @api.constrains('vehicle_id', 'school_id')
    def _check_vehicle_school(self):
        for route in self:
            if route.vehicle_id and route.vehicle_id.school_id != route.school_id:
                raise ValidationError(_(
                    'The vehicle does not belong to the selected school.'))


class SchoolTransportStop(models.Model):
    _name = 'school.transport.stop'
    _description = 'Transport Stop'
    _order = 'route_id, sequence, id'

    route_id = fields.Many2one(
        'school.transport.route', string='Route', required=True,
        ondelete='cascade', index=True)
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    pickup_time = fields.Float(help='Pickup time in hours, e.g. 6.5 for 06:30')
    dropoff_time = fields.Float(help='Drop-off time in hours, e.g. 15.5 for 15:30')

    _stop_uniq = models.Constraint(
        'UNIQUE(route_id, name)',
        'The stop already exists on this route.',
    )

    @api.depends('name', 'route_id.name', 'pickup_time')
    def _compute_display_name(self):
        for stop in self:
            stop.display_name = '%s - %s' % (
                stop.route_id.name or '', stop.name or '')
