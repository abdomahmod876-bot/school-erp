from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolGrade(models.Model):
    _name = 'school.grade'
    _description = 'School Grade'
    _order = 'stage_id, sequence, name'

    name = fields.Char(required=True, help='e.g. Grade 1, Grade 2')
    code = fields.Char()
    sequence = fields.Integer(default=10)
    stage_id = fields.Many2one('school.stage', required=True, ondelete='restrict', index=True)
    school_id = fields.Many2one(
        'school.school', related='stage_id.school_id',
        store=True, readonly=True, index=True)
    curriculum_id = fields.Many2one(
        'school.curriculum', string='Curriculum',
        domain="[('school_id', '=', school_id)]")
    subject_line_ids = fields.One2many('school.grade.subject', 'grade_id', string='Subjects')
    section_ids = fields.One2many('school.section', 'grade_id', string='Sections')
    active = fields.Boolean(default=True)

    _name_stage_uniq = models.Constraint(
        'UNIQUE(name, stage_id)',
        'The grade name must be unique per stage.',
    )

    @api.constrains('curriculum_id', 'school_id')
    def _check_curriculum_school(self):
        for grade in self:
            if grade.curriculum_id and grade.curriculum_id.school_id != grade.school_id:
                raise ValidationError(
                    _('The curriculum %(curriculum)s does not belong to the school %(school)s.',
                      curriculum=grade.curriculum_id.display_name,
                      school=grade.school_id.display_name))
