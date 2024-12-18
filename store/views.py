from django.shortcuts import render
from django.http import JsonResponse
import json
import datetime
from django.shortcuts import get_object_or_404
from .models import Order, ShippingAddress

from .models import *
from . utils import cookieCart, cartData, guestOrder


def store(request):
    data = cartData(request)
    cartItems = data['cartItems']

    products = Product.objects.all()
    context = {'products' : products, 'cartItems':cartItems}
    return render(request, 'store/store.html' ,context)

def cart(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

    context = {'items':items, 'order':order,'cartItems':cartItems }
    return render(request, 'store/cart.html' ,context)

def checkout(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

   
    context = {'items':items, 'order':order, 'cartItems':cartItems }
    return render(request, 'store/checkout.html' ,context)

def updateItem(request):
    data = json.loads(request.body)
    productId = data['productId']
    action = data['action']
    print('Action:', action)
    print('Product:', productId)
    
    customer = request.user.customer
    product = Product.objects.get(id=productId)
    order, created = Order.objects.get_or_create(customer=customer, complete=False)

    orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

    if action == 'add':
        orderItem.quantity = (orderItem.quantity + 1)
    elif action == 'remove':
        orderItem.quantity = (orderItem.quantity - 1)

    orderItem.save()

    if orderItem.quantity <= 0:
        orderItem.delete()
    return JsonResponse('Item was added', safe=False)

def processOrder(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)  # Parse JSON data
            user_data = data.get('form')  # User data from the form (including total)
            shipping_info = data.get('shipping')  # Shipping information from the form

            # Create a unique transaction ID based on timestamp
            transaction_id = datetime.datetime.now().timestamp()

            if request.user.is_authenticated:
                customer = request.user.customer
                # Update customer details if necessary
                if user_data.get('name') and user_data.get('name') != customer.name:
                    customer.name = user_data.get('name')
                if user_data.get('email') and user_data.get('email') != customer.email:
                    customer.email = user_data.get('email')
                customer.save()  # Save the updated customer

                # Get or create an open order for the customer
                order, created = Order.objects.get_or_create(customer=customer, complete=False)
            else:
                # For guest users, create a new customer object
                if not user_data.get('name') or not user_data.get('email'):
                    return JsonResponse({'message': 'Name and email are required for guest checkout'}, status=400)

                customer, created = Customer.objects.get_or_create(
                    email=user_data.get('email'),
                    defaults={'name': user_data.get('name')}
                )
                # Create the guest order for the new customer
                order = Order.objects.create(customer=customer, complete=False)

            # Ensure the total from the form matches the cart total
            try:
                total = float(user_data.get('total', 0))
            except (TypeError, ValueError):
                return JsonResponse({'message': 'Invalid total value'}, status=400)

            # Check if the form's total matches the order's cart total
            if round(total, 2) == round(float(order.get_cart_total), 2):
                order.complete = True
                order.transaction_id = transaction_id
                order.save()
                print(f"Order {order.id} saved with complete status: {order.complete}")

                # If shipping is required, create the ShippingAddress
                if order.shipping:
                    # Check if shipping_info is provided in the POST data
                    if shipping_info:
                        ShippingAddress.objects.create(
                            customer=customer,
                            order=order,
                            address=shipping_info.get('address'),
                            city=shipping_info.get('city'),
                            state=shipping_info.get('state'),
                            zipcode=shipping_info.get('zipcode'),
                             # Assuming you also have a country field
                        )
                    else:
                        return JsonResponse({'message': 'Shipping information is missing'}, status=400)

                # Clear the cart by deleting associated OrderItems
                order.orderitem_set.all().delete()

                print(f"Order {order.id} has been completed with transaction ID {transaction_id}")
                return JsonResponse({'message': 'Payment complete!'}, status=200)

            return JsonResponse({'message': 'Payment failed due to mismatched total'}, status=400)

        except json.JSONDecodeError as e:
            return JsonResponse({'message': 'Invalid JSON', 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'message': 'An error occurred', 'error': str(e)}, status=400)

    return JsonResponse({'message': 'Invalid request method'}, status=400)