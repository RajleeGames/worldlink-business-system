from decimal import Decimal
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class CompanySetting(TimeStampedModel):
    company_name = models.CharField(max_length=150, default="WORLDLINK SECURITY SYSTEMS")
    tagline = models.CharField(max_length=180, blank=True, default="Linking security to every corner")
    phone = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=200, blank=True, default="Moshi, Kilimanjaro, Tanzania")
    currency = models.CharField(max_length=10, default="TZS")
    logo = models.FileField(
        upload_to="company/",
        blank=True,
        validators=[FileExtensionValidator(["png", "jpg", "jpeg", "webp"])],
    )
    def __str__(self): return self.company_name

class Customer(TimeStampedModel):
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=220, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class MoneyAccount(TimeStampedModel):
    class Type(models.TextChoices):
        CASH="cash","Cash"
        MOBILE="mobile","Mobile Money"
        BANK="bank","Bank"
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=20, choices=Type.choices)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name
    @property
    def current_balance(self):
        incoming = self.payments.exclude(transaction__status="void").aggregate(v=models.Sum("amount"))["v"] or Decimal("0")
        expense = self.expenses.aggregate(v=models.Sum("amount"))["v"] or Decimal("0")
        purchases = self.stock_purchases.aggregate(v=models.Sum(models.F("quantity") * models.F("unit_cost"), output_field=models.DecimalField(max_digits=14, decimal_places=2)))["v"] or Decimal("0")
        transfer_in = self.transfers_in.aggregate(v=models.Sum("amount"))["v"] or Decimal("0")
        transfer_out = self.transfers_out.aggregate(v=models.Sum("amount"))["v"] or Decimal("0")
        return self.opening_balance + incoming + transfer_in - expense - purchases - transfer_out

class Service(TimeStampedModel):
    category = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=160, unique=True)
    default_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Product(TimeStampedModel):
    sku = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=120, blank=True)
    cost_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name
    @property
    def stock_value(self): return self.quantity * self.cost_price

class StockPurchase(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchases")
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey(MoneyAccount, on_delete=models.PROTECT, related_name="stock_purchases")
    supplier = models.CharField(max_length=160, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_purchases_created")
    @property
    def total(self): return self.quantity * self.unit_cost
    def __str__(self): return f"{self.product} x {self.quantity}"

class Project(TimeStampedModel):
    class Status(models.TextChoices):
        QUOTATION="quotation","Quotation"
        ACTIVE="active","Active"
        COMPLETED="completed","Completed"
        CANCELLED="cancelled","Cancelled"
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=200)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="projects")
    quoted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUOTATION)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    def __str__(self): return f"{self.code} - {self.title}"
    @property
    def direct_costs(self):
        expenses = self.expenses.aggregate(v=models.Sum("amount"))["v"] or Decimal("0")
        line_costs = TransactionLine.objects.filter(transaction__project=self).exclude(transaction__status="void").aggregate(v=models.Sum(models.F("quantity") * models.F("unit_cost"), output_field=models.DecimalField(max_digits=14, decimal_places=2)))["v"] or Decimal("0")
        return expenses + line_costs
    @property
    def revenue(self): return self.transactions.exclude(status="void").aggregate(v=models.Sum("total"))["v"] or Decimal("0")
    @property
    def profit(self): return self.revenue - self.direct_costs

class Transaction(TimeStampedModel):
    class Kind(models.TextChoices):
        SALE="sale","Product Sale"
        SERVICE="service","Quick Service"
        PROJECT="project","Project / Installation"
        MAINTENANCE="maintenance","Maintenance / Support"
    class Status(models.TextChoices):
        PAID="paid","Paid"
        PARTIAL="partial","Partially Paid"
        UNPAID="unpaid","Unpaid"
        VOID="void","Void"
    number = models.CharField(max_length=40, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="transactions", null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, related_name="transactions", null=True, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    description = models.CharField(max_length=255, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions_created")
    void_reason = models.CharField(max_length=255, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    def __str__(self): return self.number
    @property
    def amount_paid(self): return self.payments.aggregate(v=models.Sum("amount"))["v"] or Decimal("0")
    @property
    def balance(self): return max(Decimal("0"), self.total - self.amount_paid)
    @property
    def cost_total(self):
        return self.lines.aggregate(
            v=models.Sum(
                models.F("quantity") * models.F("unit_cost"),
                output_field=models.DecimalField(max_digits=14, decimal_places=2),
            )
        )["v"] or Decimal("0")
    @property
    def gross_profit(self): return self.total - self.cost_total
    @property
    def margin_percent(self):
        if self.total <= 0:
            return Decimal("0")
        return (self.gross_profit / self.total) * Decimal("100")
    def refresh_status(self):
        if self.status == self.Status.VOID: return
        paid = self.amount_paid
        self.status = self.Status.PAID if paid >= self.total and self.total > 0 else self.Status.PARTIAL if paid > 0 else self.Status.UNPAID
        self.save(update_fields=["status", "updated_at"])

class TransactionLine(TimeStampedModel):
    class LineType(models.TextChoices):
        PRODUCT="product","Product"
        SERVICE="service","Service"
        CUSTOM="custom","Custom"
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="lines")
    line_type = models.CharField(max_length=20, choices=LineType.choices)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.PROTECT, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    @property
    def line_total(self): return self.quantity * self.unit_price
    @property
    def line_cost(self): return self.quantity * self.unit_cost

class Payment(TimeStampedModel):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="payments")
    account = models.ForeignKey(MoneyAccount, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments_received")

class ExpenseCategory(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    def __str__(self): return self.name

class Expense(TimeStampedModel):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey(MoneyAccount, on_delete=models.PROTECT, related_name="expenses")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, related_name="expenses", null=True, blank=True)
    spent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="expenses_created")
    receipt_reference = models.CharField(max_length=120, blank=True)

class MoneyTransfer(TimeStampedModel):
    from_account = models.ForeignKey(MoneyAccount, on_delete=models.PROTECT, related_name="transfers_out")
    to_account = models.ForeignKey(MoneyAccount, on_delete=models.PROTECT, related_name="transfers_in")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

class DayClose(TimeStampedModel):
    date = models.DateField(default=timezone.localdate, unique=True)
    opening_cash = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expected_cash = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actual_cash = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    @property
    def difference(self): return self.actual_cash - self.expected_cash

class AuditLog(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=120)
    detail = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    def __str__(self): return f"{self.action} - {self.created_at:%Y-%m-%d %H:%M}"
