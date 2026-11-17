{
    'name': 'School Management Student Portal',
    'version': '19.0.1.1.0',
    'category': 'Education',
    'summary': 'Portal for students: fees, attendance, results and timetable',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': [
        'portal',
        'school_core',
        'school_student',
        'school_parent_portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/school_student_portal_rules.xml',
        'views/portal_templates.xml',
        'views/portal_home.xml',
    ],
    'demo': [
        'demo/portal_demo.xml',
    ],
    'installable': True,
    'application': False,
}
