
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
)
from django.shortcuts import get_object_or_404, render

from .models import (
    Product,
    StockPurchase,
    Transaction,
    TransactionLine,
)
from .stock_analytics import (
    prepare_stock_product,
    stock_summary,
)


SORT_OPTIONS = {
    "newest": "-id",
    "oldest": "id",
    "name": "name",
    "name_desc": "-name",
    "sku": "sku",
    "quantity_high": "-quantity",
    "quantity_low": "quantity",
    "cost_high": "-cost_price",
    "price_high": "-selling_price",
    "value_high": "-calculated_stock_value",
    "profit_high": "-calculated_stock_profit",
}


@login_required
def products(request):
    q = (request.GET.get("q") or "").strip()[:120]
    category = (request.GET.get("category") or "").strip()
    stock = (request.GET.get("stock") or "all").strip()
    state = (request.GET.get("state") or "active").strip()
    profit = (request.GET.get("profit") or "all").strip()
    sort = (request.GET.get("sort") or "newest").strip()

    if stock not in ("all", "good", "low", "out"):
        stock = "all"

    if state not in ("all", "active", "inactive"):
        state = "active"

    if profit not in ("all", "gain", "loss", "even"):
        profit = "all"

    if sort not in SORT_OPTIONS:
        sort = "newest"

    try:
        page_size = int(request.GET.get("page_size", 20))
    except (TypeError, ValueError):
        page_size = 20

    if page_size not in (20, 50, 100):
        page_size = 20

    categories = list(
        Product.objects.exclude(category="")
        .order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )

    qs = Product.objects.all()

    if state == "active":
        qs = qs.filter(is_active=True)
    elif state == "inactive":
        qs = qs.filter(is_active=False)

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(sku__icontains=q)
            | Q(category__icontains=q)
        )

    if category:
        qs = qs.filter(category=category)

    if stock == "out":
        qs = qs.filter(quantity__lte=0)

    elif stock == "low":
        qs = qs.filter(
            quantity__gt=0,
            quantity__lte=F("reorder_level"),
        )

   
    elif stock == "good":
        qs = qs.filter(
            quantity__gt=0
        ).filter(
            quantity__gt=F("reorder_level")
        )


    if profit == "gain":
        qs = qs.filter(
            selling_price__gt=F("cost_price")
        )

    elif profit == "loss":
        qs = qs.filter(
            selling_price__lt=F("cost_price")
        )

    elif profit == "even":
        qs = qs.filter(
            selling_price=F("cost_price")
        )

    money_field = DecimalField(
        max_digits=32,
        decimal_places=2,
    )

    qs = qs.annotate(
        calculated_stock_value=ExpressionWrapper(
            F("quantity") * F("cost_price"),
            output_field=money_field,
        ),
        calculated_stock_profit=ExpressionWrapper(
            F("quantity") * (
                F("selling_price") - F("cost_price")
            ),
            output_field=money_field,
        ),
    )

    # The overall stock position is not affected by search.
    overall_stats = stock_summary()

    # Search totals include only active matching products.
    filtered_stats = stock_summary(
        qs.filter(is_active=True)
    )

    qs = qs.order_by(
        SORT_OPTIONS[sort],
        "id",
    )

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    for product in page_obj.object_list:
        prepare_stock_product(product)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "items": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "query_params": params.urlencode(),
        "q": q,
        "category": category,
        "categories": categories,
        "stock": stock,
        "state": state,
        "profit": profit,
        "sort": sort,
        "page_size": page_size,
        "overall_stats": overall_stats,
        "filtered_stats": filtered_stats,
        "sort_options": [
            ("newest", "Newest first"),
            ("oldest", "Oldest first"),
            ("name", "Name A-Z"),
            ("name_desc", "Name Z-A"),
            ("sku", "SKU A-Z"),
            ("quantity_high", "Highest quantity"),
            ("quantity_low", "Lowest quantity"),
            ("cost_high", "Highest buying price"),
            ("price_high", "Highest selling price"),
            ("value_high", "Highest stock value"),
            ("profit_high", "Highest potential profit"),
        ],
    }

    return render(
        request,
        "inventory/products.html",
        context,
    )


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    prepare_stock_product(product)

    purchases = (
        StockPurchase.objects
        .filter(product=product)
        .select_related("account", "created_by")
        .order_by("-created_at")[:12]
    )

    sales = list(
        TransactionLine.objects
        .filter(product=product, line_type=TransactionLine.LineType.PRODUCT, unit_price__gt=0)
        .exclude(
            transaction__status=Transaction.Status.VOID
        )
        .select_related("transaction")
        .order_by("-created_at")[:12]
    )

    # Internal office sales use CUSTOM + Product FK; zero-priced PRODUCT
    # rows created in V1 remain legacy office materials.
    materials = list(
        TransactionLine.objects
        .filter(product=product, transaction__kind__in=[
            Transaction.Kind.SERVICE, Transaction.Kind.MAINTENANCE, Transaction.Kind.PROJECT
        ])
        .filter(Q(line_type=TransactionLine.LineType.CUSTOM) |
                Q(line_type=TransactionLine.LineType.PRODUCT, unit_price=0))
        .exclude(transaction__status=Transaction.Status.VOID)
        .select_related("transaction")
        .order_by("-created_at")[:12]
    )

    recent_sold_quantity = sum(
        (line.quantity for line in sales),
        Decimal("0"),
    )

    recent_sales_value = sum(
        (
            line.quantity * line.unit_price
            for line in sales
        ),
        Decimal("0"),
    )

    forecasts = []

    for percentage in (25, 50, 75, 100):
        ratio = Decimal(percentage) / Decimal("100")

        forecasts.append({
            "percentage": percentage,
            "quantity": max(
                product.quantity, Decimal("0")
            ) * ratio,
            "revenue": product.stock_retail_value * ratio,
            "profit": product.stock_profit_value * ratio,
        })

    context = {
        "product": product,
        "purchases": purchases,
        "sales": sales,
        "materials": materials,
        "recent_sold_quantity": recent_sold_quantity,
        "recent_sales_value": recent_sales_value,
        "forecasts": forecasts,
    }

    return render(
        request,
        "inventory/product_detail.html",
        context,
    )
