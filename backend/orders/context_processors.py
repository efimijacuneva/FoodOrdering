from .models import Cart, Order


def app_context(request):
    ctx = {'cart_count': 0, 'pending_count': 0}

    try:
        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                return ctx
            cart = Cart.objects.get(session_key=session_key, user=None)
        ctx['cart_count'] = cart.get_item_count()
    except Cart.DoesNotExist:
        pass
    except Exception:
        pass

    if request.user.is_authenticated and request.user.is_staff:
        ctx['pending_count'] = Order.objects.filter(status='PENDING').count()

    return ctx
