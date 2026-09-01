from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.forms import ProfileForm, UserCreateForm, UserUpdateForm
from accounts.models import User
from .decorators import admin_required
from .forms import (
    CompanySettingForm,
    CustomerForm,
    DayCloseForm,
    ExpenseForm,
    MoneyAccountForm,
    ProductForm,
    ProjectForm,
    TransactionCreateForm,
    ServiceForm,
    StockPurchaseForm,
    TransferForm,
)
from .models import (
    AuditLog,
    CompanySetting,
    Customer,
    DayClose,
    Expense,
    MoneyAccount,
    MoneyTransfer,
    Payment,
    Product,
    Project,
    Service,
    StockPurchase,
    Transaction,
    TransactionLine,
)
from .utils import audit


def _sum(qs, field="amount"):
    return qs.aggregate(v=Sum(field))["v"] or Decimal("0")


def _render_form_page(
    request,
    form,
    *,
    title,
    subtitle,
    submit_label,
    cancel_url,
    eyebrow="",
    multipart=False,
):
    return render(
        request,
        "shared/form_page.html",
        {
            "form": form,
            "form_title": title,
            "form_subtitle": subtitle,
            "submit_label": submit_label,
            "cancel_url": cancel_url,
            "eyebrow": eyebrow,
            "multipart": multipart,
        },
    )


def _delete_page(request, obj, *, title, subtitle, cancel_url, success_url, audit_label):
    if request.method == "POST":
        text = str(obj)
        try:
            obj.delete()
        except ProtectedError:
            messages.error(
                request,
                "This record is already used by other business records. Mark it inactive instead of deleting it.",
            )
            return redirect(cancel_url)
        audit(request, audit_label, text)
        messages.success(request, f"{text} deleted.")
        return redirect(success_url)
    return render(
        request,
        "shared/confirm_delete.html",
        {"object": obj, "delete_title": title, "delete_subtitle": subtitle, "cancel_url": cancel_url},
    )


@login_required
def dashboard(request):
    today = timezone.localdate()
    tx = Transaction.objects.exclude(status=Transaction.Status.VOID)

    # Admins can inspect any dashboard period. Cashiers stay focused on today.
    is_admin = bool(getattr(request.user, "is_company_admin", False))
    range_key = (request.GET.get("range") or "month").strip().lower() if is_admin else "today"

    presets = {
        "today": (today, today),
        "7d": (today - timedelta(days=6), today),
        "month": (today.replace(day=1), today),
        "year": (today.replace(month=1, day=1), today),
    }

    filter_start, filter_end = presets.get(range_key, presets["month"] if is_admin else presets["today"])

    if is_admin and range_key == "custom":
        raw_start = (request.GET.get("date_from") or "").strip()
        raw_end = (request.GET.get("date_to") or "").strip()
        try:
            custom_start = date.fromisoformat(raw_start)
            custom_end = date.fromisoformat(raw_end)
            if custom_start > custom_end:
                custom_start, custom_end = custom_end, custom_start
            # Future dates add no business value to this historical dashboard.
            custom_end = min(custom_end, today)
            custom_start = min(custom_start, custom_end)
            # Keep an accidental huge range from making the browser chart unusable.
            if (custom_end - custom_start).days > 730:
                custom_start = custom_end - timedelta(days=730)
            filter_start, filter_end = custom_start, custom_end
        except ValueError:
            range_key = "month"
            filter_start, filter_end = presets["month"]

    period_tx_qs = (
        tx.filter(created_at__date__range=(filter_start, filter_end))
        .select_related("customer", "created_by")
        .prefetch_related("lines")
        .order_by("-created_at")
    )
    period_transactions = list(period_tx_qs)
    period_expenses = list(
        Expense.objects.filter(created_at__date__range=(filter_start, filter_end)).order_by("created_at")
    )

    revenue = sum((item.total for item in period_transactions), Decimal("0"))
    cogs = sum(
        (
            sum((line.line_cost for line in item.lines.all()), Decimal("0"))
            for item in period_transactions
        ),
        Decimal("0"),
    )
    expenses = sum((item.amount for item in period_expenses), Decimal("0"))
    gross = revenue - cogs
    net = gross - expenses

    # Build one efficient in-memory time series from the already-fetched period data.
    tx_by_day = {}
    for item in period_transactions:
        key = timezone.localdate(item.created_at)
        bucket = tx_by_day.setdefault(key, {"revenue": Decimal("0"), "cogs": Decimal("0")})
        bucket["revenue"] += item.total
        bucket["cogs"] += sum((line.line_cost for line in item.lines.all()), Decimal("0"))

    expense_by_day = {}
    for item in period_expenses:
        key = timezone.localdate(item.created_at)
        expense_by_day[key] = expense_by_day.get(key, Decimal("0")) + item.amount

    period_days = (filter_end - filter_start).days + 1
    trend_labels = []
    trend_revenue = []
    trend_gross = []
    trend_expenses = []
    trend_net = []

    # Daily points remain excellent for custom/short ranges. Longer ranges are
    # grouped monthly so a full-year dashboard stays readable and fast.
    if period_days <= 62:
        cursor = filter_start
        while cursor <= filter_end:
            tx_bucket = tx_by_day.get(cursor, {})
            day_revenue = tx_bucket.get("revenue", Decimal("0"))
            day_cogs = tx_bucket.get("cogs", Decimal("0"))
            day_expenses = expense_by_day.get(cursor, Decimal("0"))
            day_gross = day_revenue - day_cogs

            trend_labels.append(f"{cursor.day} {cursor.strftime('%b')}")
            trend_revenue.append(float(day_revenue))
            trend_gross.append(float(day_gross))
            trend_expenses.append(float(day_expenses))
            trend_net.append(float(day_gross - day_expenses))
            cursor += timedelta(days=1)
        trend_granularity = "Daily"
    else:
        monthly = {}
        for day_key, values in tx_by_day.items():
            key = (day_key.year, day_key.month)
            bucket = monthly.setdefault(
                key,
                {"revenue": Decimal("0"), "cogs": Decimal("0"), "expenses": Decimal("0")},
            )
            bucket["revenue"] += values["revenue"]
            bucket["cogs"] += values["cogs"]
        for day_key, amount in expense_by_day.items():
            key = (day_key.year, day_key.month)
            bucket = monthly.setdefault(
                key,
                {"revenue": Decimal("0"), "cogs": Decimal("0"), "expenses": Decimal("0")},
            )
            bucket["expenses"] += amount

        cursor = filter_start.replace(day=1)
        last_month = filter_end.replace(day=1)
        while cursor <= last_month:
            key = (cursor.year, cursor.month)
            bucket = monthly.get(
                key,
                {"revenue": Decimal("0"), "cogs": Decimal("0"), "expenses": Decimal("0")},
            )
            month_revenue = bucket["revenue"]
            month_gross = month_revenue - bucket["cogs"]
            month_expenses = bucket["expenses"]

            trend_labels.append(cursor.strftime("%b %Y"))
            trend_revenue.append(float(month_revenue))
            trend_gross.append(float(month_gross))
            trend_expenses.append(float(month_expenses))
            trend_net.append(float(month_gross - month_expenses))

            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)
        trend_granularity = "Monthly"

    kind_totals = {value: Decimal("0") for value, _label in Transaction.Kind.choices}
    for item in period_transactions:
        kind_totals[item.kind] = kind_totals.get(item.kind, Decimal("0")) + item.total

    kind_labels = []
    kind_values = []
    for value, label in Transaction.Kind.choices:
        total = kind_totals.get(value, Decimal("0"))
        if total > 0:
            kind_labels.append(label)
            kind_values.append(float(total))

    if filter_start == filter_end:
        period_label = filter_start.strftime("%d %b %Y")
    elif filter_start.year == filter_end.year:
        period_label = f"{filter_start.strftime('%d %b')} – {filter_end.strftime('%d %b %Y')}"
    else:
        period_label = f"{filter_start.strftime('%d %b %Y')} – {filter_end.strftime('%d %b %Y')}"

    context = {
        "today_revenue": revenue,
        "today_expenses": expenses,
        "today_gross": gross,
        "today_net": net,
        "debts": sum((item.balance for item in tx.exclude(status=Transaction.Status.PAID)), Decimal("0")),
        "month_revenue": revenue,
        "month_expenses": expenses,
        "month_net": net,
        "recent": period_transactions[:8],
        "accounts": MoneyAccount.objects.filter(is_active=True),
        "active_projects": Project.objects.filter(status=Project.Status.ACTIVE).count(),
        "trend_chart": {
            "labels": trend_labels,
            "revenue": trend_revenue,
            "gross": trend_gross,
            "expenses": trend_expenses,
            "net": trend_net,
        },
        "trend_start": filter_start,
        "trend_end": filter_end,
        "trend_granularity": trend_granularity,
        "kind_chart": {"labels": kind_labels, "values": kind_values},
        "filter_start": filter_start,
        "filter_end": filter_end,
        "range_key": range_key,
        "period_label": period_label,
        "period_days": period_days,
        "period_transaction_count": len(period_transactions),
        "dashboard_filter_enabled": is_admin,
    }
    return render(request, "dashboard/index.html", context)


def _catalog_context():
    products = [
        {
            "id": item.pk,
            "type": "product",
            "name": item.name,
            "sku": item.sku,
            "category": item.category or "Product",
            "price": str(item.selling_price),
            "cost": str(item.cost_price),
            "stock": str(item.quantity),
        }
        for item in Product.objects.filter(is_active=True).order_by("name")
    ]
    services = [
        {
            "id": item.pk,
            "type": "service",
            "name": item.name,
            "sku": "",
            "category": item.category or "Service",
            "price": str(item.default_price),
            "cost": "0",
            "stock": "",
        }
        for item in Service.objects.filter(is_active=True).order_by("name")
    ]
    return products, services


def _safe_line_draft(raw):
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    safe = []
    for item in value[:100]:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                "uid": str(item.get("uid", ""))[:80],
                "type": str(item.get("type", ""))[:20],
                "item_id": item.get("item_id"),
                "description": str(item.get("description", ""))[:255],
                "quantity": str(item.get("quantity", "1"))[:40],
                "unit_price": str(item.get("unit_price", "0"))[:40],
                "unit_cost": str(item.get("unit_cost", "0"))[:40],
            }
        )
    return safe


def _positive_decimal(value, label):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} is not a valid number.")
    if number <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return number


def _prepare_transaction_lines(raw_lines):
    if not isinstance(raw_lines, list) or not raw_lines:
        raise ValueError("Add at least one product, service or custom item.")
    if len(raw_lines) > 100:
        raise ValueError("A transaction can contain at most 100 lines.")

    product_ids = set()
    service_ids = set()
    for line in raw_lines:
        if not isinstance(line, dict):
            raise ValueError("One transaction line is invalid.")
        line_type = str(line.get("type", "")).lower()
        item_id = line.get("item_id")
        if line_type == TransactionLine.LineType.PRODUCT:
            try:
                product_ids.add(int(item_id))
            except (TypeError, ValueError):
                raise ValueError("Choose a valid product.")
        elif line_type == TransactionLine.LineType.SERVICE:
            try:
                service_ids.add(int(item_id))
            except (TypeError, ValueError):
                raise ValueError("Choose a valid saved service.")
        elif line_type != TransactionLine.LineType.CUSTOM:
            raise ValueError("Choose Product, Service or Custom for every line.")

    products = {
        item.pk: item
        for item in Product.objects.select_for_update().filter(pk__in=product_ids, is_active=True)
    }
    services = {
        item.pk: item
        for item in Service.objects.filter(pk__in=service_ids, is_active=True)
    }
    if len(products) != len(product_ids):
        raise ValueError("One selected product is unavailable or inactive.")
    if len(services) != len(service_ids):
        raise ValueError("One selected service is unavailable or inactive.")

    prepared = []
    requested_stock = {}
    subtotal = Decimal("0")

    for index, line in enumerate(raw_lines, start=1):
        line_type = str(line.get("type", "")).lower()
        quantity = _positive_decimal(line.get("quantity", "0"), f"Line {index} quantity")
        unit_price = _positive_decimal(line.get("unit_price", "0"), f"Line {index} price")
        description = str(line.get("description", "")).strip()[:255]
        product = None
        service = None
        unit_cost = Decimal("0")

        if line_type == TransactionLine.LineType.PRODUCT:
            product = products[int(line.get("item_id"))]
            description = description or product.name
            unit_cost = product.cost_price
            requested_stock[product.pk] = requested_stock.get(product.pk, Decimal("0")) + quantity
            if requested_stock[product.pk] > product.quantity:
                raise ValueError(
                    f"Not enough stock for {product.name}. Available: {product.quantity}."
                )
        elif line_type == TransactionLine.LineType.SERVICE:
            service = services[int(line.get("item_id"))]
            description = description or service.name
        else:
            if not description:
                raise ValueError(f"Line {index} needs a custom description.")

        line_total = quantity * unit_price
        subtotal += line_total
        prepared.append(
            {
                "line_type": line_type,
                "product": product,
                "service": service,
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "unit_cost": unit_cost,
            }
        )

    return prepared, products, requested_stock, subtotal


@login_required
@db_transaction.atomic
def transaction_create(request):
    form = TransactionCreateForm(request.POST or None)
    line_errors = []
    raw_json = request.POST.get("lines_json", "") if request.method == "POST" else ""
    line_draft = _safe_line_draft(raw_json)

    if request.method == "POST" and form.is_valid():
        try:
            raw_lines = json.loads(raw_json or "[]")
            prepared, locked_products, requested_stock, subtotal = _prepare_transaction_lines(raw_lines)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            line_errors.append(str(exc))
        else:
            discount = form.cleaned_data.get("discount") or Decimal("0")
            payment = form.cleaned_data.get("payment_amount") or Decimal("0")

            if discount >= subtotal:
                form.add_error("discount", "Discount must be less than the transaction subtotal.")
            else:
                total = subtotal - discount
                if payment > total:
                    form.add_error("payment_amount", "Payment cannot be greater than the transaction total.")

                customer = form.cleaned_data.get("customer")
                project = form.cleaned_data.get("project")
                if project and not customer:
                    customer = project.customer

                if total - payment > 0 and not customer:
                    form.add_error(
                        "customer",
                        "Choose a customer when any balance will remain unpaid.",
                    )

                if not form.errors:
                    summary = (
                        prepared[0]["description"]
                        if len(prepared) == 1
                        else f"{len(prepared)} transaction items"
                    )
                    note = (form.cleaned_data.get("description") or "").strip()
                    obj = Transaction.objects.create(
                        number=f"TMP-{uuid.uuid4().hex[:12]}",
                        customer=customer,
                        project=project,
                        kind=form.cleaned_data["kind"],
                        description=note or summary,
                        subtotal=subtotal,
                        discount=discount,
                        total=total,
                        created_by=request.user,
                    )
                    obj.number = f"WL-{obj.pk:06d}"
                    obj.save(update_fields=["number", "updated_at"])

                    for line in prepared:
                        TransactionLine.objects.create(transaction=obj, **line)

                    for product_id, quantity in requested_stock.items():
                        product = locked_products[product_id]
                        product.quantity -= quantity
                        product.save(update_fields=["quantity", "updated_at"])

                    if payment > 0:
                        Payment.objects.create(
                            transaction=obj,
                            account=form.cleaned_data["account"],
                            amount=payment,
                            reference=form.cleaned_data.get("reference", ""),
                            received_by=request.user,
                        )

                    obj.refresh_status()
                    audit(
                        request,
                        "Created transaction",
                        f"{obj.number} · {len(prepared)} line(s) · {total}",
                    )
                    messages.success(request, f"Transaction {obj.number} completed.")
                    return redirect("transaction_detail", pk=obj.pk)

    products_catalog, services_catalog = _catalog_context()
    context = {
        "form": form,
        "title": "New Transaction",
        "line_errors": line_errors,
        "line_draft": line_draft,
        "products_catalog": products_catalog,
        "services_catalog": services_catalog,
    }
    return render(request, "transactions/form.html", context)


@login_required
def transaction_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    kind = request.GET.get("kind", "").strip()
    range_key = (request.GET.get("range") or "all").strip().lower()
    today = timezone.localdate()

    qs = Transaction.objects.select_related("customer", "created_by").order_by("-created_at")

    if q:
        qs = qs.filter(
            Q(description__icontains=q)
            | Q(number__icontains=q)
            | Q(customer__name__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if kind:
        qs = qs.filter(kind=kind)

    presets = {
        "today": (today, today),
        "7d": (today - timedelta(days=6), today),
        "month": (today.replace(day=1), today),
        "year": (today.replace(month=1, day=1), today),
    }

    filter_start = None
    filter_end = None
    raw_start = (request.GET.get("date_from") or "").strip()
    raw_end = (request.GET.get("date_to") or "").strip()

    if range_key in presets:
        filter_start, filter_end = presets[range_key]
    elif range_key == "custom":
        try:
            filter_start = date.fromisoformat(raw_start) if raw_start else None
            filter_end = date.fromisoformat(raw_end) if raw_end else None
        except ValueError:
            filter_start = None
            filter_end = None

        if filter_start and filter_end and filter_start > filter_end:
            filter_start, filter_end = filter_end, filter_start
    else:
        range_key = "all"

    if filter_start:
        qs = qs.filter(created_at__date__gte=filter_start)
    if filter_end:
        qs = qs.filter(created_at__date__lte=filter_end)

    filtered_count = qs.count()
    filtered_value = _sum(qs.exclude(status=Transaction.Status.VOID), "total")

    if range_key == "all":
        range_label = "All time"
    elif filter_start and filter_end:
        range_label = f"{filter_start:%d %b %Y} – {filter_end:%d %b %Y}"
    elif filter_start:
        range_label = f"From {filter_start:%d %b %Y}"
    elif filter_end:
        range_label = f"Up to {filter_end:%d %b %Y}"
    else:
        range_label = "Custom range"

    return render(
        request,
        "transactions/list.html",
        {
            "items": qs[:300],
            "status_choices": Transaction.Status.choices,
            "kind_choices": Transaction.Kind.choices,
            "range_key": range_key,
            "range_label": range_label,
            "filter_start": filter_start,
            "filter_end": filter_end,
            "filtered_count": filtered_count,
            "filtered_value": filtered_value,
        },
    )


@login_required
def transaction_detail(request, pk):
    obj = get_object_or_404(
        Transaction.objects.select_related("customer", "project", "created_by").prefetch_related(
            "payments__account", "lines__product", "lines__service"
        ),
        pk=pk,
    )
    return render(
        request,
        "transactions/detail.html",
        {"obj": obj, "money_accounts": MoneyAccount.objects.filter(is_active=True)},
    )


@login_required
@db_transaction.atomic
def payment_add(request, pk):
    obj = get_object_or_404(Transaction.objects.select_for_update(), pk=pk)
    if request.method == "POST" and obj.status != Transaction.Status.VOID:
        try:
            amount = Decimal(request.POST.get("amount", "0"))
            account = MoneyAccount.objects.get(pk=request.POST.get("account"), is_active=True)
        except Exception:
            messages.error(request, "Enter a valid payment and account.")
            return redirect("transaction_detail", pk=pk)
        if amount <= 0 or amount > obj.balance:
            messages.error(request, "Payment must be greater than zero and not exceed the balance.")
            return redirect("transaction_detail", pk=pk)
        Payment.objects.create(
            transaction=obj,
            account=account,
            amount=amount,
            reference=request.POST.get("reference", ""),
            received_by=request.user,
        )
        obj.refresh_status()
        audit(request, "Added payment", f"{obj.number} - {amount}")
        messages.success(request, "Payment recorded.")
    return redirect("transaction_detail", pk=pk)


@admin_required
@db_transaction.atomic
def transaction_void(request, pk):
    obj = get_object_or_404(Transaction.objects.select_for_update(), pk=pk)
    if request.method == "POST" and obj.status != Transaction.Status.VOID:
        stock_to_restore = {}
        for line in obj.lines.all():
            if line.product_id:
                stock_to_restore[line.product_id] = stock_to_restore.get(line.product_id, Decimal("0")) + line.quantity
        for product in Product.objects.select_for_update().filter(pk__in=stock_to_restore):
            product.quantity += stock_to_restore[product.pk]
            product.save(update_fields=["quantity", "updated_at"])
        obj.status = Transaction.Status.VOID
        obj.void_reason = request.POST.get("reason", "").strip() or "Voided by admin"
        obj.voided_at = timezone.now()
        obj.save()
        audit(request, "Voided transaction", obj.number)
        messages.success(request, "Transaction voided, stock restored, and the audit trail was retained.")
    return redirect("transaction_detail", pk=pk)


# Customers -----------------------------------------------------------------
@login_required
def customers(request):
    return render(request, "customers/index.html", {"items": Customer.objects.order_by("-id")[:300]})


@login_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Created customer", str(obj))
        messages.success(request, "Customer saved.")
        return redirect("customers")
    return _render_form_page(
        request,
        form,
        title="New customer",
        subtitle="Add a customer, company or organization.",
        submit_label="Save Customer",
        cancel_url=reverse("customers"),
        eyebrow="Customers",
    )


@login_required
def customer_edit(request, pk):
    obj = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Updated customer", str(obj))
        messages.success(request, "Customer updated.")
        return redirect("customers")
    return _render_form_page(
        request,
        form,
        title="Edit customer",
        subtitle="Update customer contact details and status.",
        submit_label="Save Changes",
        cancel_url=reverse("customers"),
        eyebrow="Customers",
    )


@admin_required
def customer_delete(request, pk):
    obj = get_object_or_404(Customer, pk=pk)
    return _delete_page(
        request,
        obj,
        title="Delete customer?",
        subtitle="Customers already used on transactions or projects cannot be deleted.",
        cancel_url=reverse("customers"),
        success_url=reverse("customers"),
        audit_label="Deleted customer",
    )


# Products ------------------------------------------------------------------
@login_required
def products(request):
    return render(request, "inventory/products.html", {"items": Product.objects.order_by("-id")[:300]})


@admin_required
def product_create(request):
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Created product", str(obj))
        messages.success(request, "Product saved.")
        return redirect("products")
    return _render_form_page(
        request,
        form,
        title="New product",
        subtitle="Create stock equipment with cost, selling price and reorder level.",
        submit_label="Save Product",
        cancel_url=reverse("products"),
        eyebrow="Inventory",
    )


@admin_required
def product_edit(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Updated product", str(obj))
        messages.success(request, "Product updated.")
        return redirect("products")
    return _render_form_page(
        request,
        form,
        title="Edit product",
        subtitle="Update product information. Use Purchases for normal stock additions.",
        submit_label="Save Changes",
        cancel_url=reverse("products"),
        eyebrow="Inventory",
    )


@admin_required
def product_delete(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    return _delete_page(
        request,
        obj,
        title="Delete product?",
        subtitle="A product used by a transaction cannot be deleted. You can mark it inactive instead.",
        cancel_url=reverse("products"),
        success_url=reverse("products"),
        audit_label="Deleted product",
    )


# Services ------------------------------------------------------------------
@login_required
def services(request):
    return render(request, "inventory/services.html", {"items": Service.objects.order_by("-id")[:300]})


@admin_required
def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Created service", str(obj))
        messages.success(request, "Service saved.")
        return redirect("services")
    return _render_form_page(
        request,
        form,
        title="New saved service",
        subtitle="Create a reusable service for fast transaction entry.",
        submit_label="Save Service",
        cancel_url=reverse("services"),
        eyebrow="Services",
    )


@admin_required
def service_edit(request, pk):
    obj = get_object_or_404(Service, pk=pk)
    form = ServiceForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Updated service", str(obj))
        messages.success(request, "Service updated.")
        return redirect("services")
    return _render_form_page(
        request,
        form,
        title="Edit saved service",
        subtitle="Update the category, default price or availability.",
        submit_label="Save Changes",
        cancel_url=reverse("services"),
        eyebrow="Services",
    )


@admin_required
def service_delete(request, pk):
    obj = get_object_or_404(Service, pk=pk)
    return _delete_page(
        request,
        obj,
        title="Delete saved service?",
        subtitle="Services already used on transactions cannot be deleted. Mark them inactive instead.",
        cancel_url=reverse("services"),
        success_url=reverse("services"),
        audit_label="Deleted service",
    )


# Expenses ------------------------------------------------------------------
@login_required
def expenses(request):
    items = Expense.objects.select_related("category", "account", "project", "spent_by").order_by("-created_at")[:300]
    return render(request, "expenses/index.html", {"items": items})


@login_required
def expense_create(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.spent_by = request.user
        obj.save()
        audit(request, "Created expense", f"{obj.description} - {obj.amount}")
        messages.success(request, "Expense recorded.")
        return redirect("expenses")
    return _render_form_page(
        request,
        form,
        title="New expense",
        subtitle="Record company spending and the account used to pay it.",
        submit_label="Record Expense",
        cancel_url=reverse("expenses"),
        eyebrow="Finance",
    )


@admin_required
def expense_edit(request, pk):
    obj = get_object_or_404(Expense, pk=pk)
    form = ExpenseForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Updated expense", f"#{obj.pk} {obj.description} - {obj.amount}")
        messages.success(request, "Expense updated.")
        return redirect("expenses")
    return _render_form_page(
        request,
        form,
        title="Edit expense",
        subtitle="Correct this expense. The change will remain visible in the audit log.",
        submit_label="Save Changes",
        cancel_url=reverse("expenses"),
        eyebrow="Finance",
    )


@admin_required
def expense_delete(request, pk):
    obj = get_object_or_404(Expense, pk=pk)
    return _delete_page(
        request,
        obj,
        title="Delete expense?",
        subtitle="This permanently removes the expense and changes account balances and reports.",
        cancel_url=reverse("expenses"),
        success_url=reverse("expenses"),
        audit_label="Deleted expense",
    )


# Projects ------------------------------------------------------------------
@login_required
def projects(request):
    return render(request, "projects/index.html", {"items": Project.objects.select_related("customer").order_by("-id")[:300]})


@login_required
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Created project", str(obj))
        messages.success(request, "Project saved.")
        return redirect("projects")
    return _render_form_page(
        request,
        form,
        title="New project",
        subtitle="Create a quotation, installation or customer job for project costing.",
        submit_label="Save Project",
        cancel_url=reverse("projects"),
        eyebrow="Projects",
    )


@login_required
def project_edit(request, pk):
    obj = get_object_or_404(Project, pk=pk)
    form = ProjectForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Updated project", str(obj))
        messages.success(request, "Project updated.")
        return redirect("projects")
    return _render_form_page(
        request,
        form,
        title="Edit project",
        subtitle="Update project dates, amount, status and notes.",
        submit_label="Save Changes",
        cancel_url=reverse("projects"),
        eyebrow="Projects",
    )


@admin_required
def project_delete(request, pk):
    obj = get_object_or_404(Project, pk=pk)
    return _delete_page(
        request,
        obj,
        title="Delete project?",
        subtitle="Deleting a project will not delete its transactions or expenses; those records will remain.",
        cancel_url=reverse("projects"),
        success_url=reverse("projects"),
        audit_label="Deleted project",
    )


# Purchases -----------------------------------------------------------------
@admin_required
def purchases(request):
    items = StockPurchase.objects.select_related("product", "account", "created_by").order_by("-created_at")[:300]
    return render(request, "inventory/purchases.html", {"items": items, "title": "Purchases"})


@admin_required
@db_transaction.atomic
def purchase_create(request):
    form = StockPurchaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        product = obj.product
        product.quantity += obj.quantity
        product.cost_price = obj.unit_cost
        product.save(update_fields=["quantity", "cost_price", "updated_at"])
        audit(request, "Recorded stock purchase", f"{product.name} x {obj.quantity}")
        messages.success(request, "Purchase recorded and stock increased.")
        return redirect("purchases")
    return _render_form_page(
        request,
        form,
        title="New stock purchase",
        subtitle="Add purchased stock and reduce the selected company money account.",
        submit_label="Record Purchase",
        cancel_url=reverse("purchases"),
        eyebrow="Inventory",
    )


# Money ---------------------------------------------------------------------
@admin_required
def money_accounts(request):
    return render(request, "money/accounts.html", {"items": MoneyAccount.objects.order_by("id")})


@admin_required
def money_account_create(request):
    form = MoneyAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Created money account", str(obj))
        messages.success(request, "Money account saved.")
        return redirect("money_accounts")
    return _render_form_page(
        request,
        form,
        title="New money account",
        subtitle="Add cash, mobile money or bank balances used by WorldLink.",
        submit_label="Save Account",
        cancel_url=reverse("money_accounts"),
        eyebrow="Finance",
    )


@admin_required
def money_account_edit(request, pk):
    obj = get_object_or_404(MoneyAccount, pk=pk)
    form = MoneyAccountForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Updated money account", str(obj))
        messages.success(request, "Money account updated.")
        return redirect("money_accounts")
    return _render_form_page(
        request,
        form,
        title="Edit money account",
        subtitle="Update account name, type, opening balance or status.",
        submit_label="Save Changes",
        cancel_url=reverse("money_accounts"),
        eyebrow="Finance",
    )


@admin_required
def transfers(request):
    form = TransferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        audit(request, "Created transfer", f"{obj.from_account} → {obj.to_account}: {obj.amount}")
        messages.success(request, "Transfer recorded.")
        return redirect("transfers")
    return render(
        request,
        "money/transfers.html",
        {"form": form, "items": MoneyTransfer.objects.select_related("from_account", "to_account", "created_by").order_by("-created_at")[:200], "title": "Money Transfers"},
    )


@login_required
def debts(request):
    items = [
        item
        for item in Transaction.objects.exclude(status__in=[Transaction.Status.PAID, Transaction.Status.VOID])
        .select_related("customer")
        .order_by("-created_at")
        if item.balance > 0
    ]
    return render(request, "transactions/debts.html", {"items": items, "total_debt": sum((x.balance for x in items), Decimal("0"))})


@admin_required
def reports(request):
    today = timezone.localdate()
    start = request.GET.get("start") or today.replace(day=1).isoformat()
    end = request.GET.get("end") or today.isoformat()
    tx = Transaction.objects.exclude(status=Transaction.Status.VOID).filter(created_at__date__range=[start, end]).prefetch_related("lines")
    ex = Expense.objects.filter(created_at__date__range=[start, end])
    revenue = _sum(tx, "total")
    expenses_total = _sum(ex)
    cogs = sum((sum((line.line_cost for line in item.lines.all()), Decimal("0")) for item in tx), Decimal("0"))
    kinds = []
    for value, label in Transaction.Kind.choices:
        subset = tx.filter(kind=value)
        total = _sum(subset, "total")
        if subset.exists():
            kinds.append({"label": label, "count": subset.count(), "total": total})
    expense_categories = [
        {"label": row["category__name"], "total": row["total"]}
        for row in ex.values("category__name").annotate(total=Sum("amount")).order_by("-total")
    ]
    return render(
        request,
        "reports/index.html",
        {
            "start": start,
            "end": end,
            "revenue": revenue,
            "expenses": expenses_total,
            "cogs": cogs,
            "net": revenue - cogs - expenses_total,
            "transactions": tx.count(),
            "kind_breakdown": kinds,
            "expense_categories": expense_categories,
            "accounts": MoneyAccount.objects.filter(is_active=True),
        },
    )


@login_required
def day_close(request):
    today = timezone.localdate()
    cash = MoneyAccount.objects.filter(account_type=MoneyAccount.Type.CASH, is_active=True).first()
    previous = DayClose.objects.filter(date__lt=today).order_by("-date").first()
    opening = previous.actual_cash if previous else (cash.opening_balance if cash else Decimal("0"))
    cash_in = (
        cash.payments.exclude(transaction__status=Transaction.Status.VOID).filter(created_at__date=today).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        if cash
        else Decimal("0")
    )
    cash_expenses = (
        cash.expenses.filter(created_at__date=today).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        if cash
        else Decimal("0")
    )
    purchase_total = Decimal("0")
    if cash:
        for purchase in cash.stock_purchases.filter(created_at__date=today):
            purchase_total += purchase.total
    transfer_in = (
        cash.transfers_in.filter(created_at__date=today).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        if cash
        else Decimal("0")
    )
    transfer_out = (
        cash.transfers_out.filter(created_at__date=today).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        if cash
        else Decimal("0")
    )
    expected = opening + cash_in + transfer_in - cash_expenses - purchase_total - transfer_out
    form = DayCloseForm(request.POST or None, initial={"date": today, "opening_cash": opening, "expected_cash": expected})
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.closed_by = request.user
        obj.save()
        audit(request, "Closed day", str(obj.date))
        messages.success(request, "Day closing saved.")
        return redirect("day_close")
    return render(
        request,
        "dayclose/index.html",
        {
            "form": form,
            "items": DayClose.objects.order_by("-date")[:60],
            "cash_account": cash,
            "cash_in": cash_in,
            "cash_out": cash_expenses + purchase_total + transfer_out,
            "transfer_in": transfer_in,
            "opening": opening,
            "expected": expected,
        },
    )


@admin_required
def ledger(request):
    entries = []
    for payment in Payment.objects.exclude(transaction__status=Transaction.Status.VOID).select_related("transaction", "account", "received_by").order_by("-created_at")[:500]:
        entries.append({"date": payment.created_at, "type": "Income", "description": f"{payment.transaction.number} · {payment.transaction.description}", "account": payment.account.name, "amount": payment.amount, "direction": "in"})
    for expense in Expense.objects.select_related("category", "account").order_by("-created_at")[:500]:
        entries.append({"date": expense.created_at, "type": "Expense", "description": f"{expense.category.name} · {expense.description}", "account": expense.account.name, "amount": expense.amount, "direction": "out"})
    for purchase in StockPurchase.objects.select_related("product", "account").order_by("-created_at")[:500]:
        entries.append({"date": purchase.created_at, "type": "Stock Purchase", "description": purchase.product.name, "account": purchase.account.name, "amount": purchase.total, "direction": "out"})
    for transfer in MoneyTransfer.objects.select_related("from_account", "to_account").order_by("-created_at")[:500]:
        entries.append({"date": transfer.created_at, "type": "Transfer", "description": f"{transfer.from_account.name} → {transfer.to_account.name}", "account": "Internal", "amount": transfer.amount, "direction": "transfer"})
    entries.sort(key=lambda x: x["date"], reverse=True)
    return render(request, "money/ledger.html", {"entries": entries[:500]})


# System / users ------------------------------------------------------------
@admin_required
def admin_panel(request):
    company = CompanySetting.objects.first() or CompanySetting.objects.create()
    return render(
        request,
        "adminpanel/index.html",
        {
            "company_obj": company,
            "users": User.objects.order_by("username"),
            "logs": AuditLog.objects.select_related("user").order_by("-created_at")[:80],
        },
    )


@admin_required
def company_settings(request):
    company = CompanySetting.objects.first() or CompanySetting.objects.create()
    form = CompanySettingForm(request.POST or None, request.FILES or None, instance=company)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        audit(request, "Updated company settings", obj.company_name)
        messages.success(request, "Company settings updated.")
        return redirect("admin_panel")
    return _render_form_page(
        request,
        form,
        title="Company settings",
        subtitle="Branding and company details used across the dashboard and login screen.",
        submit_label="Save Settings",
        cancel_url=reverse("admin_panel"),
        eyebrow="System",
        multipart=True,
    )


@admin_required
def user_create(request):
    form = UserCreateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        audit(request, "Created user", user.username)
        messages.success(request, "User created.")
        return redirect("admin_panel")
    return _render_form_page(
        request,
        form,
        title="New user",
        subtitle="Create an Admin or Cashier account and optionally add a profile image.",
        submit_label="Create User",
        cancel_url=reverse("admin_panel"),
        eyebrow="Users",
        multipart=True,
    )


@admin_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserUpdateForm(request.POST or None, request.FILES or None, instance=user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        audit(request, "Updated user", user.username)
        messages.success(request, "User updated.")
        return redirect("admin_panel")
    return _render_form_page(
        request,
        form,
        title="Edit user",
        subtitle="Update name, role, profile image and account status.",
        submit_label="Save Changes",
        cancel_url=reverse("admin_panel"),
        eyebrow="Users",
        multipart=True,
    )


@admin_required
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, "You cannot delete the account you are currently using.")
        return redirect("admin_panel")
    return _delete_page(
        request,
        user,
        title="Delete user?",
        subtitle="Users connected to transactions, payments or audit records may need to be deactivated instead.",
        cancel_url=reverse("admin_panel"),
        success_url=reverse("admin_panel"),
        audit_label="Deleted user",
    )


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        audit(request, "Updated own profile", user.username)
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "profile/index.html", {"form": form})
