from django.contrib import admin
from .models import *
for m in [CompanySetting,Customer,MoneyAccount,Service,Product,StockPurchase,Project,Transaction,TransactionLine,Payment,ExpenseCategory,Expense,MoneyTransfer,DayClose,AuditLog]:
    admin.site.register(m)
