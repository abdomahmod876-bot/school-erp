from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolAttendanceSession(models.Model):
    _name = 'school.attendance.session'
    _inherit = ['school.mixin']
    _description = 'Attendance Register'
    _order = 'date desc, section_id, period_id'

    name = fields.Char(compute='_compute_name', store=True)
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    section_id = fields.Many2one(
        'school.section', string='Section', required=True,
        ondelete='restrict', index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', related='section_id.academic_year_id',
        store=True, readonly=True, index=True)
    period_id = fields.Many2one(
        'school.period', string='Period', ondelete='restrict',
        domain="[('school_id', '=', school_id)]")
    teacher_id = fields.Many2one(
        'school.teacher', string='Teacher', ondelete='restrict',
        domain="[('school_id', '=', school_id)]")
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done'),
        ],
        required=True, default='draft', index=True)
    line_ids = fields.One2many(
        'school.attendance.line', 'session_id', string='Attendance')
    present_count = fields.Integer(compute='_compute_counts')
    absent_count = fields.Integer(compute='_compute_counts')
    late_count = fields.Integer(compute='_compute_counts')
    excused_count = fields.Integer(compute='_compute_counts')
    note = fields.Text()

    @api.depends('date', 'section_id.name', 'section_id.grade_id.name', 'period_id.name')
    def _compute_name(self):
        for session in self:
            parts = [
                session.section_id.grade_id.name or '',
                session.section_id.name or '',
            ]
            name = ' '.join(part for part in parts if part)
            if session.date:
                name = '%s - %s' % (name, session.date)
            if session.period_id:
                name = '%s (%s)' % (name, session.period_id.name)
            session.name = name

    @api.depends('line_ids.state')
    def _compute_counts(self):
        for session in self:
            states = session.line_ids.mapped('state')
            session.present_count = states.count('present')
            session.absent_count = states.count('absent')
            session.late_count = states.count('late')
            session.excused_count = states.count('excused')

    @api.onchange('section_id')
    def _onchange_section_id(self):
        if not self.section_id:
            return
        self.school_id = self.section_id.school_id
        if self.branch_id and self.branch_id.school_id != self.school_id:
            self.branch_id = False

    @api.constrains('section_id', 'school_id')
    def _check_section_school(self):
        for session in self:
            if session.section_id.school_id != session.school_id:
                raise ValidationError(_('The section does not belong to the selected school.'))

    @api.constrains('date', 'section_id', 'period_id')
    def _check_unique_session(self):
        for session in self:
            domain = [
                ('id', '!=', session.id),
                ('date', '=', session.date),
                ('section_id', '=', session.section_id.id),
            ]
            if session.period_id:
                domain.append(('period_id', '=', session.period_id.id))
            else:
                domain.append(('period_id', '=', False))
            if self.search_count(domain):
                raise ValidationError(_(
                    'An attendance register already exists for this section, date and period.'))

    def action_load_students(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Reset the register to draft before loading students.'))
        enrollments = self.env['school.enrollment'].search([
            ('section_id', '=', self.section_id.id),
            ('academic_year_id', '=', self.academic_year_id.id),
            ('state', '=', 'active'),
        ])
        if not enrollments:
            raise UserError(_('There are no active enrollments in this section.'))
        already_loaded = self.line_ids.student_id
        commands = [
            (0, 0, {'student_id': enrollment.student_id.id, 'state': 'present'})
            for enrollment in enrollments
            if enrollment.student_id not in already_loaded
        ]
        if commands:
            self.write({'line_ids': commands})

    def action_mark_all_present(self):
        if self.filtered(lambda session: session.state != 'draft'):
            raise UserError(_('Reset the register to draft before changing attendance.'))
        self.mapped('line_ids').write({'state': 'present'})

    def action_done(self):
        for session in self:
            if not session.line_ids:
                raise UserError(_('Load the students before closing the register.'))
        self.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class SchoolAttendanceLine(models.Model):
    _name = 'school.attendance.line'
    _description = 'Attendance Line'
    _order = 'student_id'

    session_id = fields.Many2one(
        'school.attendance.session', string='Register', required=True,
        ondelete='cascade', index=True)
    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='restrict', index=True)
    school_id = fields.Many2one(
        'school.school', related='session_id.school_id',
        store=True, readonly=True, index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', related='session_id.academic_year_id',
        store=True, readonly=True, index=True)
    section_id = fields.Many2one(
        'school.section', related='session_id.section_id',
        store=True, readonly=True, index=True)
    date = fields.Date(related='session_id.date', store=True, index=True)
    state = fields.Selection(
        selection=[
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('late', 'Late'),
            ('excused', 'Excused'),
        ],
        required=True, default='present')
    remark = fields.Char()

    _session_student_uniq = models.Constraint(
        'UNIQUE(session_id, student_id)',
        'The student is already in this attendance register.',
    )

    @api.constrains('student_id', 'session_id')
    def _check_student_enrolled(self):
        for line in self:
            enrollment = self.env['school.enrollment'].search([
                ('student_id', '=', line.student_id.id),
                ('section_id', '=', line.session_id.section_id.id),
                ('academic_year_id', '=', line.session_id.academic_year_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if not enrollment:
                raise ValidationError(_(
                    'The student %(student)s is not actively enrolled in the section.',
                    student=line.student_id.name))


class SchoolSection(models.Model):
    _inherit = 'school.section'

    attendance_session_ids = fields.One2many(
        'school.attendance.session', 'section_id', string='Attendance Registers')
