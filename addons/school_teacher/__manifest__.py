{
    'name': 'School Management Teachers',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Teacher profiles, subjects and employment status',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'school_core', 'school_academic'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_teacher_rules.xml',
        'data/ir_sequence_data.xml',
        'views/teacher_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/teacher_demo.xml',
    ],
    'installable': True,
    'application': False,
}
