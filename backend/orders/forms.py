from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import CustomUser, Category, Product, Order


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'placeholder': 'Last name'}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'placeholder': '+389 70 000 000'}))

    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone and not phone.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise forms.ValidationError("Enter a valid phone number (digits, spaces, + and - only).")
        return phone


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone', 'address')
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Your default delivery address'}),
            'phone': forms.TextInput(attrs={'placeholder': '+389 70 000 000'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already in use by another account.")
        return email


class CheckoutForm(forms.Form):
    delivery_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Street and number, City, Postcode'}),
        label='Delivery Address',
    )
    phone = forms.CharField(
        max_length=20,
        label='Phone Number',
        widget=forms.TextInput(attrs={'placeholder': '+389 70 000 000'}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Allergies, special requests…'}),
        label='Order Notes',
    )
    guest_name = forms.CharField(max_length=100, required=False, label='Your Name',
                                 widget=forms.TextInput(attrs={'placeholder': 'Full name'}))
    guest_email = forms.EmailField(required=False, label='Email Address',
                                   widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            del self.fields['guest_name']
            del self.fields['guest_email']
            if user.phone:
                self.fields['phone'].initial = user.phone
            if user.address:
                self.fields['delivery_address'].initial = user.address
        else:
            self.fields['guest_name'].required = True
            self.fields['guest_email'].required = True

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise forms.ValidationError("Enter a valid phone number.")
        return phone


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description', 'image', 'is_active', 'display_order')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('category', 'name', 'description', 'price', 'image', 'is_available')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
        }

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise forms.ValidationError("Price must be greater than zero.")
        return price


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('status',)
