# -*- coding: utf-8 -*-
from django import template

from analytics.models import Analytic

register = template.Library()


@register.filter
def get(value, key, default=None):
    default = u"" if default is None else default
    return unicode(value.get(key, default))


@register.filter
def list_analytics(graph, algorithm):
    l = Analytic.objects.filter(
        algorithm=algorithm,
        dump__graph=graph).order_by('-task_start')[:10]
    return l


@register.filter
def get_iso_format(analytic):
    result = "unavailable"
    if analytic.task_start is not None:
        result = analytic.task_start.isoformat()
    return result
