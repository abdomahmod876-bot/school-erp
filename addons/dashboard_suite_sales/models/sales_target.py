import calendar
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

MANAGER_GROUP = 'dashboard_suite_core.group_dashboard_manager'
METRICS = ('amount', 'orders')


def _month_start(today):
    return date(today.year, today.month, 1)


def _month_end(today):
    return date(
        today.year, today.month,
        calendar.monthrange(today.year, today.month)[1])


class DashboardSalesTarget(models.Model):
    _name = 'dashboard.suite.sales.target'
    _description = 'Sales Target'
    _order = 'date_start desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', store=True,
        readonly=True)
    user_id = fields.Many2one(
        'res.users', string='Salesperson', index=True,
        domain=[('share', '=', False)])
    team_id = fields.Many2one('crm.team', string='Sales Team', index=True)
    date_start = fields.Date(
        required=True, default=lambda self: _month_start(
            fields.Date.context_today(self)))
    date_end = fields.Date(
        required=True, default=lambda self: _month_end(
            fields.Date.context_today(self)))
    target_amount = fields.Monetary(currency_field='currency_id')
    target_orders = fields.Integer(string='Target Orders')

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @api.depends('user_id', 'team_id', 'company_id', 'date_start', 'date_end')
    def _compute_name(self):
        for target in self:
            who = (target.user_id.name or target.team_id.name
                   or target.company_id.name or _('All salespeople'))
            period = ''
            if target.date_start and target.date_end:
                period = f' ({target.date_start} - {target.date_end})'
            target.name = f'{who}{period}'

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for target in self:
            if target.date_start and target.date_end \
                    and target.date_end < target.date_start:
                raise ValidationError(_(
                    'The end date of target "%s" cannot be earlier than its '
                    'start date.', target.name))

    @api.constrains(
        'date_start', 'date_end', 'user_id', 'team_id', 'company_id', 'active')
    def _check_overlap(self):
        for target in self:
            if not (target.date_start and target.date_end):
                continue
            domain = [
                ('id', '!=', target.id),
                ('company_id', '=', target.company_id.id),
                ('date_start', '<=', target.date_end),
                ('date_end', '>=', target.date_start),
                ('user_id', '=', target.user_id.id or False),
                ('team_id', '=', target.team_id.id or False),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    'Target "%s" overlaps an existing target for the same '
                    'scope and period.', target.name))

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------
    def _check_manager(self):
        if not self.env.su \
                and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_(
                'Only dashboard administrators can manage sales targets.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        return super().create(vals_list)

    def write(self, vals):
        self._check_manager()
        return super().write(vals)

    def unlink(self):
        self._check_manager()
        return super().unlink()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def _metric_value(self, metric='amount'):
        self.ensure_one()
        if metric == 'orders':
            return self.target_orders or None
        return float(self.target_amount or 0.0)

    @api.model
    def _find_target(self, user=None, team=None, date_value=None):
        """Return the most specific target covering ``date_value``."""
        self.check_access_rights('read')
        user = user or self.env.user
        date_value = date_value or fields.Date.context_today(self)
        domain = [
            ('company_id', '=', self.env.company.id),
            ('date_start', '<=', date_value),
            ('date_end', '>=', date_value),
        ]
        scopes = [[('user_id', '=', user.id)]]
        team_ids = team.ids if team else (
            user.crm_team_ids.ids if 'crm_team_ids' in user._fields else [])
        if team_ids:
            scopes.append([
                ('user_id', '=', False),
                ('team_id', 'in', team_ids),
            ])
        scopes.append([('user_id', '=', False), ('team_id', '=', False)])
        for scope in scopes:
            target = self.search(
                domain + scope, order='date_start desc, id desc', limit=1)
            if target:
                return target
        return self.browse()

    @api.model
    def _resolve(self, metric='amount', user=None, team=None,
                 date_value=None):
        """Return the target value for the metric, or None if unavailable."""
        target = self._find_target(
            user=user, team=team, date_value=date_value)
        if not target:
            return None
        value = target._metric_value(metric)
        if value is None:
            return None
        return float(value)
