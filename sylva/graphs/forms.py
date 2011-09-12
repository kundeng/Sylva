# -*- coding: utf-8 -*-
from django import forms
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.forms import ModelForm
from django.utils.translation import gettext as _

from data.models import Data
from graphs.models import Graph
from engines.models import Instance


class GraphForm(ModelForm):
    instance = forms.ModelChoiceField(queryset=Instance.objects.none(),
                                      empty_label=_("No instances available"),
                                      required=False)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super(GraphForm, self).__init__(*args, **kwargs)
        if user:
            instances = Instance.objects.filter(owner=user)
            self.fields["instance"].queryset = instances
            empty_label = _("Choose your backend instance")
            self.fields["instance"].empty_label = empty_label
        help_text = _("Buy a <a href='%s'>new instance</a>.") \
                    % reverse("dashboard")
        self.fields["instance"].help_text = help_text

    class Meta:
        model = Graph
        fields = ("name", "description")


class AddCollaboratorForm(forms.Form):
    new_collaborator = forms.ChoiceField(choices=User.objects.none(),
                        widget=forms.Select(attrs={'class': 'chzn-select'}))
                            
    def __init__(self, *args, **kwargs):
        graph = kwargs.pop("graph", None)
        collaborators = kwargs.pop("collaborators", [])
        super(AddCollaboratorForm, self).__init__(*args, **kwargs)
        if graph:
            no_collaborators = [(u.id, u.username) \
                    for u in User.objects.all() \
                    if u != graph.owner and u not in collaborators]
            self.fields["new_collaborator"].choices = no_collaborators