{
    'name': 'School Management Core',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Schools, branches, school access groups and isolation foundation',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/school_groups.xml',
        'security/school_rules.xml',
        'security/ir.model.access.csv',
        'views/school_school_views.xml',
        'views/school_branch_views.xml',
        'views/res_users_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/school_demo.xml',
    ],
    'installable': True,
    'application': True,
}
