{
    'name': 'Dashboard Suite Core',
    'version': '19.0.4.0.0',
    'category': 'Productivity',
    'summary': 'Reusable, secure dashboard engine: KPIs, charts, tables and progress widgets',
    'author': 'Dashboard Suite',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/dashboard_suite_groups.xml',
        'security/dashboard_suite_rules.xml',
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/widget_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dashboard_suite_core/static/lib/chartjs/chart.umd.min.js',
            'dashboard_suite_core/static/src/js/dashboard_action.js',
            'dashboard_suite_core/static/src/js/dashboard_filter_bar.js',
            'dashboard_suite_core/static/src/js/dashboard_widget.js',
            'dashboard_suite_core/static/src/xml/dashboard_action.xml',
            'dashboard_suite_core/static/src/scss/dashboard_suite.scss',
        ],
    },
    'installable': True,
    'application': True,
}
