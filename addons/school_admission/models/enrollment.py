from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolEnrollment(models.Model):
    _name = 'school.enrollment'
    _description = 'Student Enrollment'
    _order = 'academic_year_id desc, student_id'

    name = fields.Char(compute='_compute_name', store=True)
    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='cascade', index=True)
    section_id = fields.Many2one(
        'school.section', string='Section', required=True,
        ondelete='restrict', index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', related='section_id.academic_year_id',
        store=True, readonly=True, index=True)
    school_id = fields.Many2one(
        'school.school', related='section_id.school_id',
        store=True, readonly=True, index=True)
    state = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('transferred', 'Transferred'),
            ('withdrawn', 'Withdrawn'),
            ('completed', 'Completed'),
        ],
        required=True, default='active', index=True)
    enrollment_date = fields.Date(
        default=fields.Date.context_today, required=True)
    end_date = fields.Date()
    note = fields.Text()
    active = fields.Boolean(default=True)

    _student_year_uniq = models.Constraint(
        'UNIQUE(student_id, academic_year_id)',
        'A student can have only one enrollment per academic year.',
    )

    @api.depends(
        'student_id.reference', 'student_id.name',
        'section_id.name', 'section_id.grade_id.name',
        'academic_year_id.name')
    def _compute_name(self):
        for enrollment in self:
            enrollment.name = '%s - %s %s (%s)' % (
                enrollment.student_id.reference or '',
                enrollment.section_id.grade_id.name or '',
                enrollment.section_id.name or '',
                enrollment.academic_year_id.name or '',
            )

    @api.constrains('student_id', 'section_id')
    def _check_student_school(self):
        for enrollment in self:
            if enrollment.student_id.school_id != enrollment.section_id.school_id:
                raise ValidationError(_(
                    'The student and the section must belong to the same school.'))

    def action_withdraw(self):
        self.write({
            'state': 'withdrawn',
            'end_date': fields.Date.context_today(self),
        })

    def action_complete(self):
        self.write({
            'state': 'completed',
            'end_date': fields.Date.context_today(self),
        })


class SchoolSection(models.Model):
    _inherit = 'school.section'

    enrollment_ids = fields.One2many(
        'school.enrollment', 'section_id', string='Enrollments')
    student_count = fields.Integer(compute='_compute_student_count')

    @api.depends('enrollment_ids.state')
    def _compute_student_count(self):
        for section in self:
            section.student_count = len(
                section.enrollment_ids.filtered(lambda enrollment: enrollment.state == 'active'))


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    enrollment_ids = fields.One2many(
        'school.enrollment', 'student_id', string='Enrollments')
    enrollment_count = fields.Integer(compute='_compute_enrollment_count')

    @api.depends('enrollment_ids')
    def _compute_enrollment_count(self):
        for student in self:
            student.enrollment_count = len(student.enrollment_ids)
