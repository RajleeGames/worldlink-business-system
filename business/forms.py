from decimal import Decimal

from django import forms
from django.db.models import Q
from .models import (
    CompanySetting,
    Customer,
    DayClose,
    Expense,
    ManualDebt,
    ManualDebtPayment,
    MoneyAccount,
    MoneyTransfer,
    Product,
    Project,
    Service,
    StockPurchase,
    Transaction,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class CompanySettingForm(StyledModelForm):
    class Meta:
        model = CompanySetting
        fields = ["company_name", "tagline", "phone", "email", "address", "currency", "logo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["logo"].widget.attrs["accept"] = "image/png,image/jpeg,image/webp"


class CustomerForm(StyledModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "address", "notes", "is_active"]


class ManualDebtForm(StyledModelForm):
    class Meta:
        model = ManualDebt
        fields = [
            "customer",
            "debtor_name",
            "phone",
            "source_account",
            "amount",
            "debt_date",
            "disbursement_reference",
            "due_date",
            "reason",
            "notes",
        ]
        labels = {
            "customer": "Existing customer (optional)",
            "debtor_name": "Person / debtor name",
            "source_account": "Money given from account",
            "amount": "Amount lent / owed (TZS)",
            "debt_date": "Loan / debt date",
            "disbursement_reference": "Outgoing reference (optional)",
            "due_date": "Due date (optional)",
            "reason": "Reason / what the debt is for",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("name")
        source_qs = MoneyAccount.objects.filter(is_active=True)
        if self.instance and self.instance.pk and self.instance.source_account_id:
            source_qs = MoneyAccount.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.source_account_id)
            )
        self.fields["source_account"].queryset = source_qs.order_by("name")
        self.fields["source_account"].required = True
        self.fields["debtor_name"].required = False
        self.fields["debt_date"].widget = forms.DateInput(attrs={"type": "date", "class": "form-control"})
        self.fields["due_date"].widget = forms.DateInput(attrs={"type": "date", "class": "form-control"})
        self.fields["amount"].widget.attrs.update({"min": "0.01", "step": "0.01", "inputmode": "decimal"})
        self.fields["debtor_name"].widget.attrs.setdefault("placeholder", "e.g. John, Asha, ABC Company")
        self.fields["phone"].widget.attrs.setdefault("placeholder", "Optional phone number")
        self.fields["disbursement_reference"].widget.attrs.setdefault(
            "placeholder", "e.g. CRDB transfer ref, M-Pesa ID, cash voucher"
        )
        self.fields["reason"].widget.attrs.setdefault("placeholder", "e.g. Personal loan, previous service, equipment balance")

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        debtor_name = (cleaned.get("debtor_name") or "").strip()
        phone = (cleaned.get("phone") or "").strip()
        amount = cleaned.get("amount")
        source_account = cleaned.get("source_account")
        debt_date = cleaned.get("debt_date")
        due_date = cleaned.get("due_date")

        if not debtor_name and customer:
            debtor_name = customer.name
            cleaned["debtor_name"] = debtor_name

        if not debtor_name:
            self.add_error("debtor_name", "Enter the person/company name or choose an existing customer.")

        if customer and not phone and customer.phone:
            cleaned["phone"] = customer.phone

        if amount is not None and amount <= 0:
            self.add_error("amount", "Debt amount must be greater than zero.")

        if self.instance and self.instance.pk and amount is not None:
            already_paid = self.instance.amount_paid
            if amount < already_paid:
                self.add_error(
                    "amount",
                    f"Amount cannot be below the amount already paid (TZS {already_paid:,.2f}).",
                )

        if source_account and amount is not None and amount > 0:
            available = source_account.current_balance
            if (
                self.instance
                and self.instance.pk
                and self.instance.source_account_id == source_account.pk
            ):
                # current_balance already includes this debt as money-out; add the
                # old principal back before validating a correction/edit.
                available += self.instance.amount
            if amount > available:
                self.add_error(
                    "amount",
                    f"This loan is greater than the available balance in {source_account.name} "
                    f"(TZS {available:,.2f}).",
                )

        if debt_date and due_date and due_date < debt_date:
            self.add_error("due_date", "Due date cannot be earlier than the debt date.")

        return cleaned


class ManualDebtPaymentForm(StyledModelForm):
    class Meta:
        model = ManualDebtPayment
        fields = ["account", "amount", "reference", "notes"]
        labels = {
            "account": "Money account received into",
            "amount": "Payment amount (TZS)",
            "reference": "Reference (optional)",
            "notes": "Payment note (optional)",
        }

    def __init__(self, *args, debt=None, **kwargs):
        self.debt = debt
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = MoneyAccount.objects.filter(is_active=True).order_by("name")
        self.fields["amount"].widget.attrs.update({"min": "0.01", "step": "0.01", "inputmode": "decimal"})
        if debt:
            self.fields["amount"].widget.attrs["max"] = str(debt.balance)
            self.fields["amount"].help_text = f"Outstanding balance: TZS {debt.balance:,.2f}"

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is None:
            return amount
        if amount <= 0:
            raise forms.ValidationError("Payment must be greater than zero.")
        if self.debt and amount > self.debt.balance:
            raise forms.ValidationError("Payment cannot be greater than the remaining debt balance.")
        return amount


class ProductForm(StyledModelForm):
    class Meta:
        model = Product
        fields = ["sku", "name", "category", "cost_price", "selling_price", "quantity", "reorder_level", "is_active"]


class ServiceForm(StyledModelForm):
    class Meta:
        model = Service
        fields = ["category", "name", "default_price", "is_active"]


class StockPurchaseForm(StyledModelForm):
    class Meta:
        model = StockPurchase
        fields = ["product", "quantity", "unit_cost", "account", "supplier", "reference"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("quantity") is not None and cleaned["quantity"] <= 0:
            self.add_error("quantity", "Quantity must be greater than zero.")
        if cleaned.get("unit_cost") is not None and cleaned["unit_cost"] < 0:
            self.add_error("unit_cost", "Unit cost cannot be negative.")
        return cleaned


class MoneyAccountForm(StyledModelForm):
    class Meta:
        model = MoneyAccount
        fields = ["name", "account_type", "opening_balance", "is_active"]


class ExpenseForm(StyledModelForm):
    class Meta:
        model = Expense
        fields = ["category", "description", "amount", "account", "project", "receipt_reference"]


class ProjectForm(StyledModelForm):
    class Meta:
        model = Project
        fields = ["code", "title", "customer", "quoted_amount", "status", "start_date", "due_date", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_date"].widget = forms.DateInput(attrs={"type": "date", "class": "form-control"})
        self.fields["due_date"].widget = forms.DateInput(attrs={"type": "date", "class": "form-control"})


class TransferForm(StyledModelForm):
    class Meta:
        model = MoneyTransfer
        fields = ["from_account", "to_account", "amount", "reference"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("from_account") and cleaned.get("to_account") and cleaned["from_account"] == cleaned["to_account"]:
            raise forms.ValidationError("Source and destination accounts must be different.")
        if cleaned.get("from_account") and cleaned.get("amount") and cleaned["amount"] > cleaned["from_account"].current_balance:
            self.add_error("amount", "This transfer is greater than the source account balance.")
        return cleaned


class DayCloseForm(StyledModelForm):
    class Meta:
        model = DayClose
        fields = ["date", "opening_cash", "expected_cash", "actual_cash", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].widget = forms.DateInput(attrs={"type": "date", "class": "form-control"})


class TransactionCreateForm(forms.Form):
    kind = forms.ChoiceField(
        choices=Transaction.Kind.choices,
        widget=forms.Select(attrs={"class": "form-control", "data-role": "transaction-kind"}),
    )
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        required=False,
        empty_label="Walk-in customer",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        required=False,
        empty_label="No project",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    description = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Optional note for this transaction",
            }
        ),
    )
    discount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "inputmode": "decimal",
                "data-role": "transaction-discount",
            }
        ),
    )
    payment_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "inputmode": "decimal",
                "data-role": "transaction-payment",
            }
        ),
    )
    account = forms.ModelChoiceField(
        queryset=MoneyAccount.objects.none(),
        required=False,
        empty_label="Select money account",
        widget=forms.Select(attrs={"class": "form-control", "data-role": "payment-account"}),
    )
    reference = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Receipt, bank or mobile reference",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("name")
        self.fields["project"].queryset = (
            Project.objects.exclude(status=Project.Status.CANCELLED)
            .select_related("customer")
            .order_by("-id")
        )
        self.fields["account"].queryset = MoneyAccount.objects.filter(is_active=True).order_by("name")

    def clean(self):
        cleaned = super().clean()
        payment = cleaned.get("payment_amount") or 0
        account = cleaned.get("account")
        kind = cleaned.get("kind")
        project = cleaned.get("project")
        customer = cleaned.get("customer")

        if payment > 0 and not account:
            self.add_error("account", "Choose where the payment was received.")

        if kind == Transaction.Kind.PROJECT and not project:
            self.add_error("project", "Choose the project for a project transaction.")

        if project and customer and project.customer_id != customer.id:
            self.add_error("customer", "The selected customer does not match this project.")

        return cleaned


# Keep the old import name working for any code that still references it.
QuickTransactionForm = TransactionCreateForm
