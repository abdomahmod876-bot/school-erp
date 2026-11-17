from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolSection(models.Model):
    _name = 'school.section'
    _description = 'Class Section'
    _order = 'grade_id, name'

    name = fields.Char(required=True, help='e.g. A, B or 1/A')
    grade_id = fields.Many2one('school.grade', required=True, ondelete='restrict', index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', required=True, ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    school_id = fields.Many2one(
        'school.school', related='grade_id.school_id',
        store=True, readonly=True, index=True)
    capacity = fields.Integer(default=30)
    room = fields.Char()
    note = fields.Text()
    active = fields.Boolean(default=True)

    _section_uniq = models.Constraint(
        'UNIQUE(grade_id, academic_year_id, name)',
        'The section name must be unique per grade and academic year.',
    )

    @api.depends('name', 'grade_id.name', 'academic_year_id.name')
    def _compute_display_name(self):
        for section in self:
            grade = section.grade_id.name or ''
            year = section.academic_year_id.name
            if year:
                section.display_name = f"{grade} / {section.name} ({year})"
            else:
                section.display_name = f"{grade} / {section.name}"

    @api.constrains('grade_id', 'academic_year_id')
    def _check_academic_year_school(self):
        for section in self:
            if section.grade_id.school_id != section.academic_year_id.school_id:
                raise ValidationError(
                    _('The academic year %(year)s does not belong to the school of the grade %(grade)s.',
                      year=section.academic_year_id.display_name,
                      grade=section.grade_id.display_name))
