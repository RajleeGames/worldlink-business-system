
from decimal import Decimal

from .models import Product


ZERO = Decimal("0")
HUNDRED = Decimal("100")


def prepare_stock_product(product):
    """Add calculated inventory values to one product."""
    qty = max(product.quantity, ZERO)

    product.stock_cost_value = qty * product.cost_price
    product.stock_retail_value = qty * product.selling_price
    product.stock_profit_value = (
        product.stock_retail_value - product.stock_cost_value
    )

    product.unit_profit = (
        product.selling_price - product.cost_price
    )

    product.margin_percent = (
        product.unit_profit / product.selling_price * HUNDRED
        if product.selling_price > ZERO
        else ZERO
    )

    if product.quantity <= ZERO:
        product.stock_state = "out"
        product.stock_label = "Out of stock"
    elif product.quantity <= product.reorder_level:
        product.stock_state = "low"
        product.stock_label = "Low stock"
    else:
        product.stock_state = "good"
        product.stock_label = "In stock"

    return product


def stock_summary(products=None):
    """
    Live current-stock valuation.

    Default: active products only.
    Uses stored Product.quantity, cost_price and selling_price.
    """

    if products is None:
        products = Product.objects.filter(is_active=True)

    cost_value = ZERO
    retail_value = ZERO
    quantity_total = ZERO

    product_count = 0
    in_stock_count = 0
    low_stock_count = 0
    out_of_stock_count = 0
    loss_price_count = 0

    rows = products.values_list(
        "quantity",
        "cost_price",
        "selling_price",
        "reorder_level",
    )

    for quantity, cost, selling, reorder in rows:
        product_count += 1

        qty = max(quantity, ZERO)

        quantity_total += qty
        cost_value += qty * cost
        retail_value += qty * selling

        if quantity <= ZERO:
            out_of_stock_count += 1
        elif quantity <= reorder:
            low_stock_count += 1
        else:
            in_stock_count += 1

        if selling < cost:
            loss_price_count += 1

    potential_profit = retail_value - cost_value

    margin = (
        potential_profit / retail_value * HUNDRED
        if retail_value > ZERO
        else ZERO
    )

    markup = (
        potential_profit / cost_value * HUNDRED
        if cost_value > ZERO
        else ZERO
    )

    forecast = []

    for percentage in (25, 50, 75, 100):
        ratio = Decimal(percentage) / HUNDRED

        forecast.append({
            "percentage": percentage,
            "revenue": retail_value * ratio,
            "cost": cost_value * ratio,
            "profit": potential_profit * ratio,
        })

    return {
        "product_count": product_count,
        "in_stock_count": in_stock_count,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "loss_price_count": loss_price_count,
        "quantity_total": quantity_total,
        "cost_value": cost_value,
        "retail_value": retail_value,
        "potential_profit": potential_profit,
        "margin": margin,
        "markup": markup,
        "forecast": forecast,
    }
