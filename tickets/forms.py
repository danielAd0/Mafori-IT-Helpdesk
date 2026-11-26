from django import forms

from .models import Category, Location, Ticket


class TicketForm(forms.ModelForm):
    """What an employee fills in. Requester and status are set by the view, never by the form."""

    class Meta:
        model = Ticket
        fields = ["subject", "category", "priority", "description", "asset_tag", "location"]
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Retired categories and locations can't be chosen for new tickets
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["category"].empty_label = "Choose a category"
        self.fields["location"].queryset = Location.objects.filter(is_active=True)
        self.fields["location"].empty_label = "Choose a location"
