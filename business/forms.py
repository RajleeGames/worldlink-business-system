from django import forms
from .models import (
    CompanySetting,
    Customer,
    DayClose,
    Expense,
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
