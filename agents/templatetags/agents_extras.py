from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permet d'accéder à la valeur d'un dictionnaire via une clé variable dans un template.
    Usage: {{ my_dict|get_item:my_key }}
    """
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None
