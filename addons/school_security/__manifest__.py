{
    'name': 'School Management Security',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'School access administration and audit trail',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['school_core'],
    'data': [
        'security/ir.model.access.csv',
        'views/access_log_views.xml',
        'views/access_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/security_demo.xml',
    ],
    'installable': True,
    'application': False,
}
