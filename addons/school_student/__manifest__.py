{
    'name': 'School Management Students',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student files, guardians and portal user links',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'school_core'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_student_rules.xml',
        'data/ir_sequence_data.xml',
        'views/student_views.xml',
        'views/guardian_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/student_demo.xml',
    ],
    'installable': True,
    'application': False,
}
