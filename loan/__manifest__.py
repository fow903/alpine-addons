{
    'name': "Administración de Prestámos",

    'summary': """
    """,

    'description': """
    """,

    'author': "Edwin de los Santos",
    'category': 'Account',
    'version': '10.0',

    'depends': ['base','account'],

    'data': [
        'security/ir.model.access.csv',
        'views/account_loan.xml',
        'wizard/wizard_pay_due.xml',
        'data/data.xml'
    ],
    'demo': [],
    'images': 'static/description/main.png',
}
