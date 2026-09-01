from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("transactions/", views.transaction_list, name="transaction_list"),
    path("transactions/new/", views.transaction_create, name="transaction_create"),
    path("transactions/<int:pk>/", views.transaction_detail, name="transaction_detail"),
    path("transactions/<int:pk>/payment/", views.payment_add, name="payment_add"),
    path("transactions/<int:pk>/void/", views.transaction_void, name="transaction_void"),

    path("customers/", views.customers, name="customers"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),

    path("services/", views.services, name="services"),
    path("services/new/", views.service_create, name="service_create"),
    path("services/<int:pk>/edit/", views.service_edit, name="service_edit"),
    path("services/<int:pk>/delete/", views.service_delete, name="service_delete"),

    path("products/", views.products, name="products"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),

    path("purchases/", views.purchases, name="purchases"),
    path("purchases/new/", views.purchase_create, name="purchase_create"),

    path("expenses/", views.expenses, name="expenses"),
    path("expenses/new/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),

    path("projects/", views.projects, name="projects"),
    path("projects/new/", views.project_create, name="project_create"),
    path("projects/<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("projects/<int:pk>/delete/", views.project_delete, name="project_delete"),

    path("debts/", views.debts, name="debts"),

    path("money/accounts/", views.money_accounts, name="money_accounts"),
    path("money/accounts/new/", views.money_account_create, name="money_account_create"),
    path("money/accounts/<int:pk>/edit/", views.money_account_edit, name="money_account_edit"),
    path("money/transfers/", views.transfers, name="transfers"),
    path("money/ledger/", views.ledger, name="ledger"),

    path("reports/", views.reports, name="reports"),
    path("day-close/", views.day_close, name="day_close"),

    path("profile/", views.profile, name="profile"),
    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path("admin-panel/company/", views.company_settings, name="company_settings"),
    path("admin-panel/users/new/", views.user_create, name="user_create"),
    path("admin-panel/users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("admin-panel/users/<int:pk>/delete/", views.user_delete, name="user_delete"),
]
