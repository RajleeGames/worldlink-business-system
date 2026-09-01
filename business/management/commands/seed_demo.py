from django.core.management.base import BaseCommand
from accounts.models import User
from business.models import CompanySetting, ExpenseCategory, MoneyAccount, Service
class Command(BaseCommand):
    help="Seed WorldLink V1 starter data"
    def handle(self,*args,**opts):
        CompanySetting.objects.get_or_create(id=1,defaults={"company_name":"WORLDLINK SECURITY SYSTEMS","tagline":"Linking security to every corner","address":"Moshi, Kilimanjaro, Tanzania"})
        for name,typ in [("Cash in Office","cash"),("M-Pesa","mobile"),("Mixx by Yas","mobile"),("Airtel Money","mobile"),("CRDB Bank","bank"),("NMB Bank","bank")]: MoneyAccount.objects.get_or_create(name=name,defaults={"account_type":typ})
        for name in ["Transport / Fuel","Tools & Equipment","Office Expenses","Internet","Electricity","Rent","Marketing","Materials / Purchases","Food / Allowance","Bank / Mobile Charges","Repairs","Tax / Fees","Miscellaneous"]: ExpenseCategory.objects.get_or_create(name=name)
        for category,name,price in [("CCTV","CCTV Camera Repair",30000),("CCTV","CCTV Installation Service",100000),("Networking","Router Configuration",30000),("Networking","Network Troubleshooting",50000),("Computers","Windows / Software Installation",30000),("Access Control","Biometric Installation",100000),("Electric Fence","Electric Fence Service",80000),("GPS","GPS Tracker Installation",50000),("Support","Site Visit / Troubleshooting",30000)]: Service.objects.get_or_create(name=name,defaults={"category":category,"default_price":price})
        admin,created=User.objects.get_or_create(username="admin",defaults={"role":"admin","is_staff":True,"is_superuser":True,"email":"admin@worldlink.local"})
        if created: admin.set_password("admin123"); admin.save()
        cashier,created=User.objects.get_or_create(username="cashier",defaults={"role":"cashier","is_staff":False})
        if created: cashier.set_password("cashier123"); cashier.save()
        self.stdout.write(self.style.SUCCESS("Seed complete. admin/admin123 and cashier/cashier123"))
