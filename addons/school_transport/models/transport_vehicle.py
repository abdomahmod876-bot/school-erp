from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolTransportVehicle(models.Model):
    _name = 'school.transport.vehicle'
    _inherit = ['school.mixin', 'mail.thread']
    _description = 'School Vehicle'
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    plate_number = fields.Char(string='Plate Number', required=True, index=True)
    model = fields.Char(string='Vehicle Model')
    capacity = fields.Integer(required=True, default=30)
    driver_name = fields.Char()
    driver_phone = fields.Char()
    route_ids = fields.One2many(
        'school.transport.route', 'vehicle_id', string='Routes')
    note = fields.Text()
    active = fields.Boolean(default=True)

    _plate_uniq = models.Constraint(
        'UNIQUE(plate_number)',
        'The plate number must be unique.',
    )
    _capacity_check = models.Constraint(
        'CHECK(capacity >= 1)',
        'The vehicle capacity must be at least one seat.',
    )

    @api.constrains('capacity')
    def _check_capacity_routes(self):
        for vehicle in self:
            for route in vehicle.route_ids:
                running = len(route.subscription_ids.filtered(
                    lambda subscription: subscription.state == 'running'))
                if running > vehicle.capacity:
                    raise ValidationError(_(
                        'The route %(route)s already has %(running)s students, '
                        'more than the capacity of %(vehicle)s.',
                        route=route.name,
                        running=running,
                        vehicle=vehicle.name))
