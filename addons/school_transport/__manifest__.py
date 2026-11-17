{
    'name': 'School Management Transport',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'School buses, routes, stops and student subscriptions',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['mail', 'school_core', 'school_student'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_transport_rules.xml',
        'data/ir_sequence_data.xml',
        'views/vehicle_views.xml',
        'views/route_views.xml',
        'views/subscription_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/transport_demo.xml',
    ],
    'installable': True,
    'application': False,
}
