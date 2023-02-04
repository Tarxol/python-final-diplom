from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

STATE_CHOICES = (
    ('basket', 'Статус корзины'),
    ('new', 'Новый'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

USER_TYPES = (
    ('seller', 'Продавец'),
    ('client', 'Клиент(Покупатель)')
)

class Shop(models.Model):
    name = models.CharField(max_length=50, unique=True)

class Category(models.Model):
    shops = models.ManyToManyField(Shop, related_name='categories')
    name = models.CharField(max_length=50, unique=True)

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete='CASCADE')
    name = models.CharField(max_length=50)

class ProductInfo(models.Model):
    product = models.ForeignKey(Product, on_delete='CASCADE')
    shop = models.ForeignKey(Shop, on_delete='CASCADE')
    model = models.CharField(max_length=50)
    quantity = models.IntegerField()
    price = models.FloatField()
    price_rrc = models.FloatField()

class Parameter(models.Model):
    name = models.CharField(max_length=50, unique=True)

class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, on_delete='CASCADE')
    parameter = models.CharField(max_length=50)
    value = models.CharField(max_length=50, null=False)

class Order(models.Model):
    user = models.ForeignKey('User', on_delete='CASCADE')
    dt = models.DateField(auto_now=True)
    status = models.CharField(max_length=50, default='new', choices=STATE_CHOICES)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete='CASCADE')
    product = models.ForeignKey(Product, on_delete='CASCADE')
    shop = models.ForeignKey(Shop, on_delete='CASCADE')
    quantity = models.IntegerField(null=False)

class Contact(models.Model):
    type = models.CharField(max_length=50)
    user = models.ForeignKey('User', on_delete='CASCADE')
    value = models.CharField(max_length=255)

class User(AbstractUser):
    type = models.CharField(max_length=50, null=False, blank=False, choices=USER_TYPES)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)