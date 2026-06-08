from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if dictionary and hasattr(dictionary, 'get'):
        return dictionary.get(key, [])
    if isinstance(dictionary, dict):
        return dictionary.get(key, [])
    return []