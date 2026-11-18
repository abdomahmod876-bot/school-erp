"""Validation of dashboard domains.

Domains are plain JSON data supplied by dashboard editors. They are never
evaluated as Python or SQL: every leaf is checked against the field metadata of
the target model and then handed to the ORM, which queries with bound
parameters.
"""

from odoo import _
from odoo.exceptions import ValidationError

DOMAIN_OPERATORS = {
    '=', '!=', '>', '>=', '<', '<=', 'in', 'not in', 'like', 'not like',
    'ilike', 'not ilike', '=like', '=ilike', 'child_of', 'parent_of',
    'set', 'not set',
}
LOGICAL_OPERATORS = {'&', '|', '!'}
TWO_ARG_OPERATORS = {'set', 'not set'}
MAX_DOMAIN_ITEMS = 100


def resolve_domain_field(model, path):
    """Return the field record for a domain path, following relations.

    ``path`` may traverse relational fields (``partner_id.country_id``).
    Returns ``None`` for unknown fields or invalid traversals.
    """
    if not isinstance(path, str) or not path:
        return None
    field = model._fields.get(path)
    if field is not None:
        return field
    head, separator, rest = path.partition('.')
    if not separator or not rest:
        return None
    field = model._fields.get(head)
    if field is None or field.type not in (
            'many2one', 'one2many', 'many2many'):
        return None
    return resolve_domain_field(model.env[field.comodel_name], rest)


def combine_domains(*domains):
    """Return the conjunction of several domains.

    Each input domain is folded into a single expression (implicit ``AND``
    between plain leaves is made explicit) so the result is always valid in
    prefix notation.
    """
    parts = [_as_expression(domain) for domain in domains if domain]
    if not parts:
        return []
    combined = parts[0]
    for part in parts[1:]:
        combined = ['&', *combined, *part]
    return combined


def _as_expression(domain):
    domain = list(domain)
    if any(isinstance(item, str) for item in domain):
        return domain
    if len(domain) <= 1:
        return domain
    expression = domain[0]
    for leaf in domain[1:]:
        expression = ['&', expression, leaf]
    return expression


def validate_domain(model, domain, label=None):
    """Validate a structured domain for ``model`` and return it as a list.

    Raises ``ValidationError`` for malformed leaves, unsupported operators,
    unknown fields or unbalanced logical expressions. Values are not inspected:
    they are always sent to the ORM as bound parameters.
    """
    label = label or _('domain')
    if domain is None or domain is False:
        return []
    if not isinstance(domain, (list, tuple)):
        raise ValidationError(_(
            'The %(label)s must be a list of conditions.', label=label))
    if not domain:
        return []
    if len(domain) > MAX_DOMAIN_ITEMS:
        raise ValidationError(_(
            'The %(label)s is too complex (more than %(max)s items).',
            label=label, max=MAX_DOMAIN_ITEMS))

    def parse(index):
        if index >= len(domain):
            raise ValidationError(_(
                'The %(label)s contains an incomplete logical expression.',
                label=label))
        item = domain[index]
        if isinstance(item, str):
            if item not in LOGICAL_OPERATORS:
                raise ValidationError(_(
                    'Unsupported logical operator "%(operator)s" in the %(label)s.',
                    operator=item, label=label))
            if item == '!':
                return parse(index + 1)
            return parse(parse(index + 1))
        if not isinstance(item, (list, tuple)):
            raise ValidationError(_(
                'Invalid condition %(item)s in the %(label)s.',
                item=item, label=label))
        if len(item) not in (2, 3):
            raise ValidationError(_(
                'Invalid condition %(item)s in the %(label)s.',
                item=item, label=label))
        field_name, operator = item[0], item[1]
        if not isinstance(field_name, str) or not isinstance(operator, str):
            raise ValidationError(_(
                'Invalid condition %(item)s in the %(label)s.',
                item=item, label=label))
        if operator not in DOMAIN_OPERATORS:
            raise ValidationError(_(
                'Unsupported operator "%(operator)s" in the %(label)s.',
                operator=operator, label=label))
        if len(item) == 2 and operator not in TWO_ARG_OPERATORS:
            raise ValidationError(_(
                'The operator "%(operator)s" requires a value in the %(label)s.',
                operator=operator, label=label))
        if len(item) == 3 and operator in TWO_ARG_OPERATORS:
            raise ValidationError(_(
                'The operator "%(operator)s" does not take a value in the %(label)s.',
                operator=operator, label=label))
        if resolve_domain_field(model, field_name) is None:
            raise ValidationError(_(
                'Unknown field "%(field)s" in the %(label)s.',
                field=field_name, label=label))
        return index + 1

    index = 0
    while index < len(domain):
        next_index = parse(index)
        if next_index <= index:
            raise ValidationError(_(
                'The %(label)s contains an invalid logical expression.',
                label=label))
        index = next_index
    return list(domain)
