from django import forms
from .models import Order


class AdminOrderUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=Order.STATUS_CHOICES, required=False)
    admin_notes = forms.CharField(widget=forms.Textarea, required=False)
    assigned_to = forms.IntegerField(required=False)
    amount_paid = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    payment_method = forms.CharField(max_length=50, required=False)
    transaction_id = forms.CharField(max_length=100, required=False)
    payment_rejection_reason = forms.CharField(widget=forms.Textarea, required=False)


class WalkinOrderForm(forms.Form):
    customer_name = forms.CharField(max_length=100, required=False)
    customer_phone = forms.CharField(max_length=20, required=False)
    walkin_customer_id = forms.IntegerField(required=False)
    is_urgent = forms.BooleanField(required=False)
    is_physical_document = forms.BooleanField(required=False)
    physical_description = forms.CharField(max_length=500, required=False)
    physical_pages = forms.IntegerField(min_value=1, required=False)
    physical_print_type = forms.ChoiceField(
        choices=[('bw', 'B&W'), ('color', 'Color')], required=False,
    )
    physical_sides = forms.ChoiceField(
        choices=[('single', 'Single'), ('double', 'Double')], required=False,
    )
    physical_copies = forms.IntegerField(min_value=1, required=False)
    addons = forms.MultipleChoiceField(required=False)
    manual_discount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    payment_method = forms.CharField(max_length=50, required=False)
    amount_paid = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    promo_code = forms.CharField(max_length=50, required=False)
    files_config = forms.CharField(widget=forms.HiddenInput, required=False)

    def clean(self):
        cleaned = super().clean()
        walkin_id = cleaned.get('walkin_customer_id')
        name = cleaned.get('customer_name', '').strip()
        phone = cleaned.get('customer_phone', '').strip()
        if not walkin_id and (not name or not phone):
            raise forms.ValidationError('Select an existing customer or provide name and phone.')
        if not cleaned.get('is_physical_document') and not self.files.getlist('files'):
            raise forms.ValidationError('Upload at least one file or mark as physical document.')
        return cleaned


class PaymentForm(forms.Form):
    payment_method = forms.ChoiceField(choices=[
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
    ])
    transaction_id = forms.CharField(max_length=100)
    payment_screenshot = forms.ImageField(required=False)
