from django import template

register = template.Library()

@register.filter
def filter(queryset, kwarg_dict=None):
    """
    Custom filter to filter a queryset with keyword arguments provided as a dictionary.
    Usage: {{ queryset|filter:"size=some_value" }} or {{ queryset|filter:kwarg_dict }}
    """
    if kwarg_dict is None:
        return queryset.first()
    kwargs = {}
    for pair in kwarg_dict.split(','):
        if '=' in pair:
            key, value = pair.split('=', 1)
            kwargs[key] = value
    return queryset.filter(**kwargs).first()