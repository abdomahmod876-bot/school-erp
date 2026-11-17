from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolGradeSubject(models.Model):
    _name = 'school.grade.subject'
    _description = 'Grade Subject'
    _rec_name = 'subject_id'
    _order = 'grade_id, subject_id'

    grade_id = fields.Many2one(
        'school.grade', required=True, ondelete='cascade', index=True)
    subject_id = fields.Many2one(
        'school.subject', required=True, ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    school_id = fields.Many2one(
        'school.school', related='grade_id.school_id',
        store=True, readonly=True, index=True)
    weekly_hours = fields.Integer(default=4)
    max_marks = fields.Float(default=100.0)
    pass_mark = fields.Float(default=50.0)
    elective = fields.Boolean()

    _grade_subject_uniq = models.Constraint(
        'UNIQUE(grade_id, subject_id)',
        'The subject is already linked to this grade.',
    )

    @api.constrains('subject_id', 'grade_id')
    def _check_subject_school(self):
        for line in self:
            if line.subject_id.school_id != line.grade_id.school_id:
                raise ValidationError(
                    _('The subject %(subject)s does not belong to the school of the grade.',
                      subject=line.subject_id.display_name))
