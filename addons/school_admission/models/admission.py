from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolAdmission(models.Model):
    _name = 'school.admission'
    _inherit = ['school.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Admission Application'
    _order = 'id desc'
    _rec_name = 'applicant_name'

    name = fields.Char(default='New', readonly=True, copy=False, index=True)
    applicant_name = fields.Char(required=True, tracking=True)
    gender = fields.Selection(
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
        ],
        required=True)
    birth_date = fields.Date()
    national_id = fields.Char(string='National ID')
    email = fields.Char()
    phone = fields.Char()
    previous_school = fields.Char()

    guardian_name = fields.Char(required=True)
    guardian_relation = fields.Selection(
        selection=[
            ('father', 'Father'),
            ('mother', 'Mother'),
            ('guardian', 'Guardian'),
            ('other', 'Other'),
        ],
        required=True, default='father')
    guardian_phone = fields.Char()
    guardian_email = fields.Char()

    academic_year_id = fields.Many2one(
        'school.academic.year', string='Academic Year', required=True,
        ondelete='restrict', domain="[('school_id', '=', school_id)]")
    grade_id = fields.Many2one(
        'school.grade', string='Grade', required=True,
        ondelete='restrict', domain="[('school_id', '=', school_id)]")
    section_id = fields.Many2one(
        'school.section', string='Enrollment Section',
        ondelete='restrict',
        domain="[('grade_id', '=', grade_id), ('academic_year_id', '=', academic_year_id)]")

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('under_review', 'Under Review'),
            ('interview', 'Interview'),
            ('accepted', 'Accepted'),
            ('waitlisted', 'Waitlisted'),
            ('rejected', 'Rejected'),
            ('enrolled', 'Enrolled'),
        ],
        required=True, default='draft', tracking=True, index=True)
    interview_date = fields.Datetime()
    decision_note = fields.Text()

    birth_certificate = fields.Boolean(string='Birth Certificate')
    previous_report = fields.Boolean(string='Previous School Report')
    photos = fields.Boolean(string='Personal Photos')
    medical_report = fields.Boolean(string='Medical Report')
    documents_complete = fields.Boolean(compute='_compute_documents_complete')

    student_id = fields.Many2one('school.student', string='Student', readonly=True, copy=False)
    enrollment_id = fields.Many2one('school.enrollment', string='Enrollment', readonly=True, copy=False)
    note = fields.Html()

    @api.depends('birth_certificate', 'previous_report', 'photos', 'medical_report')
    def _compute_documents_complete(self):
        for application in self:
            application.documents_complete = all([
                application.birth_certificate,
                application.previous_report,
                application.photos,
                application.medical_report,
            ])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('school.admission') or 'New'
        return super().create(vals_list)

    @api.onchange('grade_id')
    def _onchange_grade_id(self):
        if not self.grade_id:
            return
        self.school_id = self.grade_id.school_id
        if self.academic_year_id and self.academic_year_id.school_id != self.grade_id.school_id:
            self.academic_year_id = False
        if self.section_id and self.section_id.grade_id != self.grade_id:
            self.section_id = False

    @api.onchange('section_id')
    def _onchange_section_id(self):
        if not self.section_id:
            return
        self.grade_id = self.section_id.grade_id
        self.academic_year_id = self.section_id.academic_year_id
        self.school_id = self.section_id.school_id

    @api.constrains('grade_id', 'academic_year_id', 'section_id', 'school_id')
    def _check_academic_consistency(self):
        for application in self:
            if application.grade_id.school_id != application.school_id:
                raise ValidationError(_('The grade does not belong to the selected school.'))
            if application.academic_year_id.school_id != application.school_id:
                raise ValidationError(_('The academic year does not belong to the selected school.'))
            section = application.section_id
            if section and (section.grade_id != application.grade_id
                            or section.academic_year_id != application.academic_year_id):
                raise ValidationError(_(
                    'The selected section does not match the grade and academic year.'))

    def action_submit(self):
        if self.filtered(lambda application: application.state != 'draft'):
            raise UserError(_('Only draft applications can be submitted.'))
        self.write({'state': 'submitted'})

    def action_start_review(self):
        self.write({'state': 'under_review'})

    def action_schedule_interview(self):
        if self.filtered(lambda application: not application.interview_date):
            raise UserError(_('Set the interview date first.'))
        self.write({'state': 'interview'})

    def action_accept(self):
        self.write({'state': 'accepted'})

    def action_waitlist(self):
        self.write({'state': 'waitlisted'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self.write({
            'state': 'draft',
            'student_id': False,
            'enrollment_id': False,
        })

    def action_enroll(self):
        self.ensure_one()
        if self.state != 'accepted':
            raise UserError(_('Only accepted applications can be enrolled.'))
        if not self.section_id:
            raise UserError(_('Select the section to enroll the applicant in.'))
        section = self.section_id
        if section.grade_id != self.grade_id or section.academic_year_id != self.academic_year_id:
            raise UserError(_('The selected section does not match the grade and academic year.'))

        student = self.env['school.student'].create(self._prepare_student_vals())
        partner = self._get_guardian_partner()
        self.env['school.student.guardian'].create({
            'student_id': student.id,
            'partner_id': partner.id,
            'relation': self.guardian_relation,
            'is_primary': True,
        })
        enrollment = self.env['school.enrollment'].create({
            'student_id': student.id,
            'section_id': section.id,
        })
        self.write({
            'student_id': student.id,
            'enrollment_id': enrollment.id,
            'state': 'enrolled',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student'),
            'res_model': 'school.student',
            'res_id': student.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _prepare_student_vals(self):
        self.ensure_one()
        return {
            'name': self.applicant_name,
            'gender': self.gender,
            'birth_date': self.birth_date,
            'national_id': self.national_id,
            'email': self.email,
            'phone': self.phone,
            'school_id': self.school_id.id,
            'branch_id': self.branch_id.id,
            'state': 'active',
        }

    def _get_guardian_partner(self):
        self.ensure_one()
        partner_model = self.env['res.partner']
        partner = partner_model.browse()
        if self.guardian_email:
            partner = partner_model.search(
                [('email', '=', self.guardian_email)], limit=1)
        if not partner and self.guardian_phone:
            partner = partner_model.search(
                [('phone', '=', self.guardian_phone)], limit=1)
        if partner:
            if not partner.is_school_guardian:
                partner.write({'is_school_guardian': True})
            return partner
        return partner_model.create({
            'name': self.guardian_name,
            'email': self.guardian_email,
            'phone': self.guardian_phone,
            'is_school_guardian': True,
        })
