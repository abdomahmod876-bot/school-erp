{
    'name': 'School Dashboard: Sales & Invoicing',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Ready-made Sales and Invoicing dashboards for the dashboard builder',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['school_dashboard', 'sale', 'account'],
    'data': [
        'security/rules.xml',
        'security/ir.model.access.csv',
        'data/business_dashboards.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
