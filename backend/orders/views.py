from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import Category, Product, Cart, CartItem, Order, OrderItem, CustomUser
from .forms import RegisterForm, ProfileForm, CheckoutForm, CategoryForm, ProductForm, OrderStatusForm


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    if not request.session.session_key:
        request.session.create()
    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key, user=None)
    return cart


def merge_guest_cart(request, user):
    """Merge guest session cart into the user's cart on login/register."""
    if not request.session.session_key:
        return
    try:
        guest_cart = Cart.objects.get(session_key=request.session.session_key, user=None)
    except Cart.DoesNotExist:
        return
    user_cart, _ = Cart.objects.get_or_create(user=user)
    for guest_item in guest_cart.items.select_related('product').all():
        existing = user_cart.items.filter(product=guest_item.product).first()
        if existing:
            existing.quantity += guest_item.quantity
            existing.save()
        else:
            guest_item.cart = user_cart
            guest_item.save()
    guest_cart.delete()


def staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        if not request.user.is_staff:
            messages.error(request, "You don't have permission to access this area.")
            return redirect('menu')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── Auth ─────────────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('menu')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            merge_guest_cart(request, user)
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created.")
            return redirect('menu')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('menu')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            merge_guest_cart(request, user)
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next', '')
            return redirect(next_url or 'menu')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'profile.html', {'form': form})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully.")
            return redirect('profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'change_password.html', {'form': form})


# ─── Menu ─────────────────────────────────────────────────────────────────────

def menu_view(request):
    categories = Category.objects.filter(is_active=True)
    products = Product.objects.filter(is_available=True, category__is_active=True).select_related('category')

    search_q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()

    if search_q:
        products = products.filter(
            Q(name__icontains=search_q) | Q(description__icontains=search_q)
        )
    if category_id:
        products = products.filter(category_id=category_id)

    cart = get_or_create_cart(request)
    cart_product_ids = set(cart.items.values_list('product_id', flat=True))

    return render(request, 'menu.html', {
        'categories': categories,
        'products': products,
        'search_q': search_q,
        'selected_category': category_id,
        'cart_product_ids': cart_product_ids,
        'cart': cart,
    })


# ─── Cart ─────────────────────────────────────────────────────────────────────

def cart_view(request):
    cart = get_or_create_cart(request)
    items = cart.items.select_related('product__category').all()
    return render(request, 'cart.html', {'cart': cart, 'items': items})


def add_to_cart_view(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_available=True)
    if request.method == 'POST':
        try:
            quantity = max(1, int(request.POST.get('quantity', 1)))
        except (ValueError, TypeError):
            quantity = 1
        notes = request.POST.get('notes', '').strip()[:200]

        cart = get_or_create_cart(request)
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product,
            defaults={'quantity': quantity, 'notes': notes},
        )
        if not created:
            item.quantity += quantity
            item.notes = notes
            item.save()

        messages.success(request, f'"{product.name}" added to your cart.')
    return redirect(request.POST.get('next', 'menu'))


def remove_from_cart_view(request, item_id):
    cart = get_or_create_cart(request)
    CartItem.objects.filter(id=item_id, cart=cart).delete()
    messages.success(request, "Item removed from cart.")
    return redirect('cart')


def update_cart_view(request, item_id):
    if request.method == 'POST':
        cart = get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            quantity = 1
        if quantity < 1:
            item.delete()
            messages.success(request, "Item removed from cart.")
        else:
            item.quantity = quantity
            item.save()
    return redirect('cart')


# ─── Checkout & Orders ────────────────────────────────────────────────────────

def checkout_view(request):
    cart = get_or_create_cart(request)
    items = cart.items.select_related('product').all()
    if not items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('menu')

    if request.method == 'POST':
        form = CheckoutForm(request.POST, user=request.user)
        if form.is_valid():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                guest_name=form.cleaned_data.get('guest_name', ''),
                guest_email=form.cleaned_data.get('guest_email', ''),
                delivery_address=form.cleaned_data['delivery_address'],
                phone=form.cleaned_data['phone'],
                notes=form.cleaned_data.get('notes', ''),
                total_price=cart.get_total(),
            )
            for cart_item in items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    product_name=cart_item.product.name,
                    product_price=cart_item.product.price,
                    quantity=cart_item.quantity,
                    notes=cart_item.notes,
                )
            cart.items.all().delete()
            return redirect('order_success', order_id=order.id)
    else:
        form = CheckoutForm(user=request.user)

    return render(request, 'checkout.html', {'form': form, 'cart': cart, 'items': items})


def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.user and order.user != request.user:
        return redirect('menu')
    return render(request, 'order_success.html', {'order': order})


@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items')
    return render(request, 'order_history.html', {'orders': orders})


@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_detail.html', {'order': order})


# ─── Admin Dashboard ──────────────────────────────────────────────────────────

@staff_required
def admin_dashboard_view(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    total_users = CustomUser.objects.filter(is_staff=False).count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_revenue = Order.objects.filter(status='DELIVERED').aggregate(
        total=Sum('total_price')
    )['total'] or 0

    orders_today = Order.objects.filter(created_at__date=today).count()
    revenue_this_week = Order.objects.filter(
        created_at__date__gte=week_ago, status='DELIVERED'
    ).aggregate(total=Sum('total_price'))['total'] or 0

    status_counts = {s: Order.objects.filter(status=s).count() for s, _ in Order.STATUS_CHOICES}
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:8]

    return render(request, 'admin_panel/dashboard.html', {
        'total_users': total_users,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'orders_today': orders_today,
        'revenue_this_week': revenue_this_week,
        'status_counts': status_counts,
        'recent_orders': recent_orders,
    })


# ─── Admin Products ───────────────────────────────────────────────────────────

@staff_required
def admin_products_view(request):
    products = Product.objects.select_related('category').order_by('category__name', 'name')
    search_q = request.GET.get('q', '').strip()
    if search_q:
        products = products.filter(Q(name__icontains=search_q) | Q(category__name__icontains=search_q))
    return render(request, 'admin_panel/products.html', {'products': products, 'search_q': search_q})


@staff_required
def admin_product_create_view(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Product created successfully.")
            return redirect('admin_products')
    else:
        form = ProductForm()
    return render(request, 'admin_panel/product_form.html', {'form': form, 'action': 'Create'})


@staff_required
def admin_product_edit_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
            return redirect('admin_products')
    else:
        form = ProductForm(instance=product)
    return render(request, 'admin_panel/product_form.html', {'form': form, 'action': 'Edit', 'product': product})


@staff_required
def admin_product_delete_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        product.delete()
        messages.success(request, f'Product "{product.name}" deleted.')
        return redirect('admin_products')
    return render(request, 'admin_panel/confirm_delete.html', {'object': product, 'object_type': 'product'})


# ─── Admin Categories ─────────────────────────────────────────────────────────

@staff_required
def admin_categories_view(request):
    categories = Category.objects.annotate(product_count=Count('products')).order_by('display_order', 'name')
    return render(request, 'admin_panel/categories.html', {'categories': categories})


@staff_required
def admin_category_create_view(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created successfully.")
            return redirect('admin_categories')
    else:
        form = CategoryForm()
    return render(request, 'admin_panel/category_form.html', {'form': form, 'action': 'Create'})


@staff_required
def admin_category_edit_view(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect('admin_categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'admin_panel/category_form.html', {'form': form, 'action': 'Edit', 'category': category})


@staff_required
def admin_category_delete_view(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, f'Category "{category.name}" deleted.')
        return redirect('admin_categories')
    return render(request, 'admin_panel/confirm_delete.html', {'object': category, 'object_type': 'category'})


# ─── Admin Orders ─────────────────────────────────────────────────────────────

@staff_required
def admin_orders_view(request):
    orders = Order.objects.select_related('user').prefetch_related('items').order_by('-created_at')
    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search_q:
        orders = orders.filter(
            Q(id__icontains=search_q) |
            Q(user__username__icontains=search_q) |
            Q(guest_name__icontains=search_q) |
            Q(guest_email__icontains=search_q) |
            Q(phone__icontains=search_q)
        )
    if status_filter:
        orders = orders.filter(status=status_filter)

    return render(request, 'admin_panel/orders.html', {
        'orders': orders,
        'search_q': search_q,
        'status_filter': status_filter,
        'status_choices': Order.STATUS_CHOICES,
    })


@staff_required
def admin_order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            old_status = order.status
            order = form.save()
            if old_status != 'ACCEPTED' and order.status == 'ACCEPTED':
                email = order.get_customer_email()
                if email:
                    try:
                        send_mail(
                            subject='Your Order Has Been Accepted — Tasty Bites',
                            message=(
                                f"Hi {order.get_customer_name()},\n\n"
                                f"Great news! Your order #{order.id} has been accepted "
                                f"and is now being prepared.\n\n"
                                f"Thank you for choosing Tasty Bites!"
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[email],
                            fail_silently=True,
                        )
                    except Exception:
                        pass
            messages.success(request, f"Order #{order.id} status updated to {order.get_status_display()}.")
            return redirect('admin_order_detail', order_id=order.id)
    else:
        form = OrderStatusForm(instance=order)
    return render(request, 'admin_panel/order_detail.html', {'order': order, 'form': form})


# ─── Admin Customers ──────────────────────────────────────────────────────────

@staff_required
def admin_customers_view(request):
    users = CustomUser.objects.filter(is_staff=False).annotate(order_count=Count('orders')).order_by('-date_joined')
    search_q = request.GET.get('q', '').strip()
    if search_q:
        users = users.filter(
            Q(username__icontains=search_q) |
            Q(email__icontains=search_q) |
            Q(first_name__icontains=search_q) |
            Q(last_name__icontains=search_q)
        )
    return render(request, 'admin_panel/customers.html', {'users': users, 'search_q': search_q})


@staff_required
def admin_customer_toggle_view(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id, is_staff=False)
    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        action = "activated" if user.is_active else "deactivated"
        messages.success(request, f"Account for {user.username} has been {action}.")
    return redirect('admin_customers')
