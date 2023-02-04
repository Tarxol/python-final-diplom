from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import authentication, permissions
from api.permissions import IsClient, IsSeller, IsOwner
from api.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem
from api.serializers import OrderItemSerializer, OrderSerializer, ContactSerializer, ProductInfoSerializer
from yaml import load as load_yaml, Loader
from ujson import loads as load_json
from django.db import IntegrityError
from django.db.models import Q, Sum, F
import pprint

# Create your views here.

from rest_framework.views import APIView


class CustomAPIView(APIView):
    def get_permissions(self):
        # Instances and returns the dict of permissions that the view requires.
        return {key: [permission() for permission in permissions] for key, permissions in self.permission_classes.items()}

    def check_permissions(self, request):
        # Gets the request method and the permissions dict, and checks the permissions defined in the key matching
        # the method.
        method = request.method.lower()
        for permission in self.get_permissions()[method]:
            if not permission.has_permission(request, self):
                self.permission_denied(
                    request, message=getattr(permission, 'message', None)
                )

class UpdateShop(CustomAPIView):
    permission_classes = {'post': [IsSeller, permissions.IsAuthenticated]}

    def post(self, request):
        with open("../../data/shop1.yaml") as stream:
            try:
                data = load_yaml(stream, Loader=Loader)
                shop_data = data['shop']
                categories = data['categories']
                goods = data['goods']
                shop, _ = Shop.objects.get_or_create(name=shop_data['shop'])
                for category_data in categories:
                    category, _ = Category.objects.get_or_create(id=category_data['id'], name=category_data['name'])
                    category.shops.add(shop.id)
                    category.save()
                for good in goods:
                    product, _ = Product.objects.get_or_create(id=good['id'], name=good['name'], category_id=good['category'])
                    product_info = ProductInfo.objects.create(
                        product=product.id,
                        shop=shop.id,
                        model=good['model'],
                        price=good['price'],
                        price_rrc=good['price_rrc'],
                        quantity=good['quantity'])
                    for name, value in good['parameters'].items():
                        parameter_object, _ = Parameter.objects.get_or_create(name=name)
                        ProductParameter.objects.create(
                            product_info=product_info.id,
                            parameter=parameter_object.id,
                            value=value)
            except yaml.YAMLError as exc:
                return Response({'status':'Error', 'message': exc})
        return Response({'status':'OK'})

class BasketView(CustomAPIView):

    permission_classes = {
        'get':[permissions.IsAuthenticated, IsClient, IsOwner],
        'post':[permissions.IsAuthenticated, IsClient, IsOwner],
        'delete':[permissions.IsAuthenticated, IsClient, IsOwner],
        'put':[permissions.IsAuthenticated, IsClient, IsOwner],        
    }

    def get(self, request, *args, **kwargs):
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    # редактировать корзину
    def post(self, request, *args, **kwargs):
        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_created = 0
                for order_item in items_dict:
                    order_item.update({'order': basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({'Status': False, 'Errors': str(error)})
                        else:
                            objects_created += 1

                    else:

                        JsonResponse({'Status': False, 'Errors': serializer.errors})
                return JsonResponse({'Status': True, 'Создано объектов': objects_created})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить товары из корзины
    def delete(self, request, *args, **kwargs):
        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # добавить позиции в корзину
    def put(self, request, *args, **kwargs):
        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_updated = 0
                for order_item in items_dict:
                    if type(order_item['id']) == int and type(order_item['quantity']) == int:
                        objects_updated += OrderItem.objects.filter(order_id=basket.id, id=order_item['id']).update(
                            quantity=order_item['quantity'])

                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class OrderView(APIView):

    permission_classes = {
        'get':[permissions.IsAuthenticated, IsClient, IsOwner],
        'post':[permissions.IsAuthenticated, IsClient, IsOwner]
    }

    # получить мои заказы
    def get(self, request, *args, **kwargs):
        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    # разместить заказ из корзины
    def post(self, request, *args, **kwargs):
        if {'id', 'contact'}.issubset(request.data):
            if request.data['id'].isdigit():
                try:
                    is_updated = Order.objects.filter(
                        user_id=request.user.id, id=request.data['id']).update(
                        contact_id=request.data['contact'],
                        state='new')
                except IntegrityError as error:
                    print(error)
                    return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы'})
                else:
                    if is_updated:
                        new_order.send(sender=self.__class__, user_id=request.user.id)
                        return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class ProductInfoView(APIView):
    def get(self, request, *args, **kwargs):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        # фильтруем и отбрасываем дуликаты
        queryset = ProductInfo.objects.filter(
            query).select_related(
            'shop', 'product__category').prefetch_related(
            'product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)

        return Response(serializer.data)
