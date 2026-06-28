from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Category, Product, Cart, CartItem, Order, OrderItem

User = get_user_model()


class AuthTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='SecurePass123!'
        )

    def test_register_page_loads(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_register_new_user(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_duplicate_email(self):
        response = self.client.post(reverse('register'), {
            'username': 'another',
            'email': 'test@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already registered')

    def test_login_valid_credentials(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_invalid_credentials(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)

    def test_profile_requires_login(self):
        response = self.client.get(reverse('profile'))
        self.assertRedirects(response, '/accounts/login/?next=/profile/')

    def test_profile_accessible_when_logged_in(self):
        self.client.login(username='testuser', password='SecurePass123!')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)


class CategoryProductTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name='Burgers', description='Juicy burgers', is_active=True
        )
        self.product = Product.objects.create(
            category=self.category,
            name='Classic Burger',
            description='A classic beef burger with all the fixings.',
            price=Decimal('8.99'),
            is_available=True,
        )
        self.unavailable = Product.objects.create(
            category=self.category,
            name='Special Burger',
            description='Seasonal special.',
            price=Decimal('12.50'),
            is_available=False,
        )

    def test_menu_page_loads(self):
        response = self.client.get(reverse('menu'))
        self.assertEqual(response.status_code, 200)

    def test_menu_shows_available_products(self):
        response = self.client.get(reverse('menu'))
        self.assertContains(response, 'Classic Burger')

    def test_menu_hides_unavailable_products(self):
        response = self.client.get(reverse('menu'))
        self.assertNotContains(response, 'Special Burger')

    def test_menu_search_by_name(self):
        response = self.client.get(reverse('menu') + '?q=Classic')
        self.assertContains(response, 'Classic Burger')

    def test_menu_search_no_results(self):
        response = self.client.get(reverse('menu') + '?q=Pizza')
        self.assertNotContains(response, 'Classic Burger')

    def test_menu_filter_by_category(self):
        response = self.client.get(reverse('menu') + f'?category={self.category.id}')
        self.assertContains(response, 'Classic Burger')

    def test_inactive_category_not_shown(self):
        self.category.is_active = False
        self.category.save()
        response = self.client.get(reverse('menu'))
        self.assertNotContains(response, 'Burgers')


class CartTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='cartuser', email='cart@example.com', password='CartPass123!'
        )
        self.category = Category.objects.create(name='Pizza', is_active=True)
        self.product = Product.objects.create(
            category=self.category,
            name='Margherita',
            description='Classic pizza.',
            price=Decimal('9.50'),
            is_available=True,
        )

    def test_cart_page_loads(self):
        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, 200)

    def test_add_to_cart(self):
        self.client.login(username='cartuser', password='CartPass123!')
        response = self.client.post(reverse('add_to_cart', args=[self.product.id]), {
            'quantity': '2',
            'notes': 'Extra cheese',
            'next': '/menu/',
        })
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.get_item_count(), 2)

    def test_add_to_cart_accumulates_quantity(self):
        self.client.login(username='cartuser', password='CartPass123!')
        self.client.post(reverse('add_to_cart', args=[self.product.id]), {'quantity': '1', 'next': '/'})
        self.client.post(reverse('add_to_cart', args=[self.product.id]), {'quantity': '2', 'next': '/'})
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.get_item_count(), 3)

    def test_remove_from_cart(self):
        self.client.login(username='cartuser', password='CartPass123!')
        self.client.post(reverse('add_to_cart', args=[self.product.id]), {'quantity': '1', 'next': '/'})
        cart = Cart.objects.get(user=self.user)
        item = cart.items.first()
        response = self.client.post(reverse('remove_from_cart', args=[item.id]))
        self.assertEqual(cart.get_item_count(), 0)

    def test_update_cart_quantity(self):
        self.client.login(username='cartuser', password='CartPass123!')
        self.client.post(reverse('add_to_cart', args=[self.product.id]), {'quantity': '1', 'next': '/'})
        cart = Cart.objects.get(user=self.user)
        item = cart.items.first()
        self.client.post(reverse('update_cart', args=[item.id]), {'quantity': '5'})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 5)

    def test_update_cart_quantity_zero_removes_item(self):
        self.client.login(username='cartuser', password='CartPass123!')
        self.client.post(reverse('add_to_cart', args=[self.product.id]), {'quantity': '1', 'next': '/'})
        cart = Cart.objects.get(user=self.user)
        item = cart.items.first()
        self.client.post(reverse('update_cart', args=[item.id]), {'quantity': '0'})
        self.assertFalse(cart.items.filter(id=item.id).exists())

    def test_cart_total(self):
        self.client.login(username='cartuser', password='CartPass123!')
        self.client.post(reverse('add_to_cart', args=[self.product.id]), {'quantity': '3', 'next': '/'})
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.get_total(), Decimal('28.50'))


class OrderTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='orderuser', email='order@example.com', password='OrderPass123!',
            phone='07012345678', address='1 Test Street, Skopje'
        )
        self.category = Category.objects.create(name='Drinks', is_active=True)
        self.product = Product.objects.create(
            category=self.category,
            name='Cola',
            description='Cold cola.',
            price=Decimal('2.00'),
            is_available=True,
        )

    def _add_to_cart(self):
        self.client.post(reverse('add_to_cart', args=[self.product.id]), {'quantity': '2', 'next': '/'})

    def test_checkout_redirects_if_cart_empty(self):
        self.client.login(username='orderuser', password='OrderPass123!')
        response = self.client.get(reverse('checkout'))
        self.assertRedirects(response, reverse('menu'))

    def test_checkout_page_loads_with_items(self):
        self.client.login(username='orderuser', password='OrderPass123!')
        self._add_to_cart()
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)

    def test_place_order_authenticated(self):
        self.client.login(username='orderuser', password='OrderPass123!')
        self._add_to_cart()
        response = self.client.post(reverse('checkout'), {
            'delivery_address': '1 Test Street, Skopje',
            'phone': '07012345678',
            'notes': '',
        })
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.total_price, Decimal('4.00'))
        self.assertEqual(order.items.count(), 1)

    def test_place_order_guest(self):
        self._add_to_cart()
        response = self.client.post(reverse('checkout'), {
            'delivery_address': '2 Guest Lane, Skopje',
            'phone': '07099999999',
            'guest_name': 'Guest User',
            'guest_email': 'guest@example.com',
            'notes': '',
        })
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertIsNone(order.user)
        self.assertEqual(order.guest_email, 'guest@example.com')

    def test_order_history_requires_login(self):
        response = self.client.get(reverse('order_history'))
        self.assertRedirects(response, '/accounts/login/?next=/orders/')

    def test_order_history_shows_user_orders(self):
        self.client.login(username='orderuser', password='OrderPass123!')
        self._add_to_cart()
        self.client.post(reverse('checkout'), {
            'delivery_address': '1 Test Street',
            'phone': '07012345678',
            'notes': '',
        })
        order = Order.objects.filter(user=self.user).first()
        response = self.client.get(reverse('order_history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{order.id}')

    def test_order_detail_accessible_by_owner(self):
        self.client.login(username='orderuser', password='OrderPass123!')
        self._add_to_cart()
        self.client.post(reverse('checkout'), {
            'delivery_address': '1 Test Street',
            'phone': '07012345678',
            'notes': '',
        })
        order = Order.objects.first()
        response = self.client.get(reverse('order_detail', args=[order.id]))
        self.assertEqual(response.status_code, 200)


class AdminPanelTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='admin', email='admin@example.com', password='AdminPass123!', is_staff=True
        )
        self.regular = User.objects.create_user(
            username='regular', email='regular@example.com', password='RegPass123!'
        )
        self.category = Category.objects.create(name='Salads', is_active=True)
        self.product = Product.objects.create(
            category=self.category, name='Caesar Salad',
            description='Fresh Caesar.', price=Decimal('7.50'), is_available=True,
        )

    def test_dashboard_requires_staff(self):
        self.client.login(username='regular', password='RegPass123!')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertRedirects(response, reverse('menu'))

    def test_dashboard_accessible_by_staff(self):
        self.client.login(username='admin', password='AdminPass123!')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_create_product(self):
        self.client.login(username='admin', password='AdminPass123!')
        response = self.client.post(reverse('admin_product_create'), {
            'category': self.category.id,
            'name': 'Greek Salad',
            'description': 'With feta.',
            'price': '6.50',
            'is_available': 'on',
        })
        self.assertTrue(Product.objects.filter(name='Greek Salad').exists())

    def test_delete_product(self):
        self.client.login(username='admin', password='AdminPass123!')
        response = self.client.post(reverse('admin_product_delete', args=[self.product.id]))
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_update_order_status(self):
        self.client.login(username='admin', password='AdminPass123!')
        order = Order.objects.create(
            delivery_address='Test', phone='123', total_price=Decimal('5.00')
        )
        self.client.post(reverse('admin_order_detail', args=[order.id]), {'status': 'ACCEPTED'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'ACCEPTED')

    def test_disable_customer_account(self):
        self.client.login(username='admin', password='AdminPass123!')
        self.client.post(reverse('admin_customer_toggle', args=[self.regular.id]))
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_active)

    def test_enable_disabled_account(self):
        self.regular.is_active = False
        self.regular.save()
        self.client.login(username='admin', password='AdminPass123!')
        self.client.post(reverse('admin_customer_toggle', args=[self.regular.id]))
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_active)
