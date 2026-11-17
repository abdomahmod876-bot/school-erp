{
    'name': 'School Management Communication',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Announcements and guardian communication log',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['mail', 'school_core', 'school_student'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_communication_rules.xml',
        'data/ir_sequence_data.xml',
        'views/announcement_views.xml',
        'views/message_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/communication_demo.xml',
    ],
    'installable': True,
    'application': False,
}
