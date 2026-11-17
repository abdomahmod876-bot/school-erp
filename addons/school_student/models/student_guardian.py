from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolStudentGuardian(models.Model):
    _name = 'school.student.guardian'
    _description = 'Student Guardian'
    _rec_name = 'partner_id'
    _order = 'student_id, is_primary desc, id'

    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Guardian', required=True,
        ondelete='cascade', index=True)
    relation = fields.Selection(
        selection=[
            ('father', 'Father'),
            ('mother', 'Mother'),
            ('guardian', 'Guardian'),
            ('other', 'Other'),
        ],
        required=True, default='father')
    is_primary = fields.Boolean(string='Primary Contact')

    _student_partner_uniq = models.Constraint(
        'UNIQUE(student_id, partner_id)',
        'The guardian is already linked to this student.',
    )

    @api.depends('partner_id.name', 'relation')
    def _compute_display_name(self):
        relations = dict(self._fields['relation'].selection)
        for line in self:
            line.display_name = '%s (%s)' % (
                line.partner_id.name or '',
                relations.get(line.relation, line.relation or ''),
            )

    @api.constrains('is_primary', 'student_id')
    def _check_single_primary(self):
        for line in self.filtered('is_primary'):
            others = line.student_id.guardian_ids.filtered(
                lambda guardian: guardian.is_primary and guardian != line)
            if others:
                raise ValidationError(
                    _('A student can have only one primary guardian.'))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        partners = lines.mapped('partner_id').filtered(
            lambda partner: not partner.is_school_guardian)
        if partners:
            partners.write({'is_school_guardian': True})
        return lines
