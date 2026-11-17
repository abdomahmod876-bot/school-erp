from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolExamResult(models.Model):
    _name = 'school.exam.result'
    _description = 'Exam Result'
    _rec_name = 'student_id'
    _order = 'schedule_id, student_id'

    schedule_id = fields.Many2one(
        'school.exam.schedule', string='Schedule', required=True,
        ondelete='cascade', index=True)
    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='restrict', index=True)
    exam_id = fields.Many2one(
        'school.exam', related='schedule_id.exam_id',
        store=True, readonly=True, index=True)
    school_id = fields.Many2one(
        'school.school', related='schedule_id.school_id',
        store=True, readonly=True, index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', related='schedule_id.academic_year_id',
        store=True, readonly=True, index=True)
    subject_id = fields.Many2one(
        'school.subject', related='schedule_id.subject_id',
        store=True, readonly=True, index=True)
    date = fields.Date(related='schedule_id.date', store=True, readonly=True)
    max_marks = fields.Float(related='schedule_id.max_marks', readonly=True)
    pass_mark = fields.Float(related='schedule_id.pass_mark', readonly=True)
    score = fields.Float(default=0.0, required=True)
    percentage = fields.Float(compute='_compute_grades', store=True, digits=(5, 2))
    grade = fields.Selection(
        selection=[
            ('a', 'A - Excellent'),
            ('b', 'B - Very Good'),
            ('c', 'C - Good'),
            ('d', 'D - Pass'),
            ('f', 'F - Fail'),
        ],
        compute='_compute_grades', store=True)
    passed = fields.Boolean(compute='_compute_grades', store=True)
    remark = fields.Char()

    _schedule_student_uniq = models.Constraint(
        'UNIQUE(schedule_id, student_id)',
        'The student already has a result for this exam subject.',
    )

    @api.depends('score', 'schedule_id.max_marks', 'schedule_id.pass_mark')
    def _compute_grades(self):
        for result in self:
            max_marks = result.schedule_id.max_marks
            percentage = (result.score / max_marks * 100.0) if max_marks else 0.0
            result.percentage = percentage
            if percentage >= 90:
                result.grade = 'a'
            elif percentage >= 80:
                result.grade = 'b'
            elif percentage >= 70:
                result.grade = 'c'
            elif percentage >= 60:
                result.grade = 'd'
            else:
                result.grade = 'f'
            result.passed = result.score >= result.schedule_id.pass_mark

    @api.constrains('score', 'schedule_id')
    def _check_score(self):
        for result in self:
            if result.score < 0 or result.score > result.schedule_id.max_marks:
                raise ValidationError(_(
                    'The score of %(student)s must be between 0 and %(max)s.',
                    student=result.student_id.name,
                    max=result.schedule_id.max_marks))

    @api.constrains('student_id', 'schedule_id')
    def _check_student_enrolled(self):
        for result in self:
            exam = result.schedule_id.exam_id
            enrollment = self.env['school.enrollment'].search([
                ('student_id', '=', result.student_id.id),
                ('academic_year_id', '=', exam.academic_year_id.id),
                ('section_id', 'in', exam.section_ids.ids),
                ('state', '=', 'active'),
            ], limit=1)
            if not enrollment:
                raise ValidationError(_(
                    'The student %(student)s is not enrolled in a section of this exam.',
                    student=result.student_id.name))


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    exam_result_ids = fields.One2many(
        'school.exam.result', 'student_id', string='Exam Results')
