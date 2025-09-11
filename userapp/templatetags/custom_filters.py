from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''



@register.filter
def has_cancelled_items(items):
    return any(item.status == 'cancelled' for item in items)