from django import template
register=template.Library()
@register.filter
def money(value):
    try: return f"{float(value):,.0f}"
    except Exception: return value
