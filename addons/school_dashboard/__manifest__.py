{
    'name': 'School Dashboard Builder',
    'version': '19.0.1.2.0',
    'category': 'Productivity',
    'summary': 'Visual dashboards: KPI tiles, charts and lists over any Odoo model',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'school_core', 'school_student'],
    'data': [
        'security/school_dashboard_rules.xml',
        'security/ir.model.access.csv',
        'views/school_dashboard_item_views.xml',
        'views/school_dashboard_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/dashboard_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'school_dashboard/static/lib/chartjs/chart.umd.min.js',
            'school_dashboard/static/src/js/dashboard_action.js',
            'school_dashboard/static/src/js/chart_card.js',
            'school_dashboard/static/src/xml/dashboard_action.xml',
            'school_dashboard/static/src/xml/chart_card.xml',
            'school_dashboard/static/src/scss/dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
}
