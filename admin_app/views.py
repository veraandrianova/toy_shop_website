from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import formset_factory
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import UpdateView, CreateView, DeleteView, FormView
from transliterate import translit

# Create your views here.
from admin_app.forms import ProductDetailForm, StocksForm, ImageProductForm, ImageProductFormSet, ImageFormSet
from app_toy_shop.models import Product, Image
from chat.models import ChatDialog
from orders.form import OrderListForm
from orders.models import Order, OrderItem
from user.models import User
from .tasks import send_for_users_phone


class ProductAdminView(LoginRequiredMixin, ListView):
    """Список всех товаров"""
    model = Product
    template_name = 'admin_app/all_product.html'
    context_object_name = "products"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class ToyDetailAdminView(LoginRequiredMixin, UpdateView):
    """ Детали одного товара"""
    model = Product
    slug_field = 'url'
    context_object_name = "product"
    template_name = 'admin_app/product_detail.html'
    form_class = ProductDetailForm
    second_form_class = ImageProductFormSet
    success_url = reverse_lazy('admin_app:all_product')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.product = Product.objects.get(url=self.kwargs.get('slug'))
        self.images = Image.objects.filter(product_id=self.product.id)
        context['product_form'] = ProductDetailForm(prefix='product_form_pre', instance=self.product)
        context['image_form'] = ImageFormSet(queryset=Image.objects.filter(product_id=self.product.id),
                                             prefix='image_form_pre')
        return context

    def post(self, request, *args, **kwargs):
        self.object = Product.objects.get(url=self.kwargs.get('slug'))
        product_form = ProductDetailForm(request.POST, request.FILES, prefix='product_form_pre')
        image_form = ImageFormSet(request.POST, request.FILES, prefix='image_form_pre')
        if product_form.is_valid():
            self.object.name = product_form.cleaned_data['name']
            self.object.description = product_form.cleaned_data['description']
            self.object.price = product_form.cleaned_data['price']
            self.object.category = product_form.cleaned_data['category']
            self.object.quantity = product_form.cleaned_data['quantity']
            self.object.is_active = product_form.cleaned_data['is_active']
            if product_form.cleaned_data['poster'] != None:
                self.object.poster = product_form.cleaned_data['poster']
            self.object.save()

        if image_form.is_valid():
            for image_f in image_form:
                product_image = image_f.save(commit=False)
                link = image_f.cleaned_data.get('link')
                if link is not None:
                    product_image.product_id = self.object.id
                    product_image.link = link
                    product_image.save()

            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(product_form=product_form))


def product_detail(request, pk):
    """Детали продуктов для администратора"""
    if request.user.is_superuser:
        product = Product.objects.get(id=pk)
        images = Image.objects.filter(product_id=product.id)
        images_product = []
        for image in images:
            link = {}
            link['link'] = image.link
            images_product.append(link)
        if request.method == 'POST':
            form = ProductDetailForm(data=request.POST, instance=product)
            form_image = ImageProductFormSet(request.POST, request.FILES, initial=images_product)
            if form.is_valid():
                form.save()
            if form_image.is_valid():
                images.delete()
                product_id = Product.objects.get(name=product.name).id
                for p in form_image:
                    product_image = p.save(commit=False)
                    link = p.cleaned_data.get('link')
                    if link is not None:
                        product_image.product_id = product_id
                        product_image.link = link
                        product_image.save()

            return redirect('admin_app:all_product')
        else:
            form = ProductDetailForm(instance=product)
            images = Image.objects.filter(product_id=product.id)
            images_product = []
            for image in images:
                link = {}
                link['link'] = image.link
                images_product.append(link)
            ImageProductFormSet2 = formset_factory(ImageProductForm, extra=3 - len(images_product))
            form_image = ImageProductFormSet2(initial=images_product)
            return render(request, 'admin_app/product_detail.html',
                          {'product': product, 'form': form, 'form_image': form_image})

    else:
        return redirect('shop:title')


class CreateProduct(LoginRequiredMixin, CreateView):
    """Добавление продукта"""
    model = Product
    success_url = reverse_lazy("admin_app:all_product")
    template_name = 'admin_app/add_product.html'
    form_class = ProductDetailForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product_form'] = ProductDetailForm(prefix='product_form_pre')
        context['image_form'] = ImageProductFormSet(prefix='image_form_pre')
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        product_form = ProductDetailForm(request.POST, request.FILES, prefix='product_form_pre')
        image_form = ImageProductFormSet(request.POST, request.FILES, prefix='image_form_pre')
        if product_form.is_valid() and image_form.is_valid():
            self.object = product_form.save(commit=False)
            name = product_form.cleaned_data['name'].lower().replace(' ', '_')
            url = translit(name, language_code='ru', reversed=True)
            self.object.url = url
            self.object.save()
            for p in image_form:
                product_image = p.save(commit=False)
                link = p.cleaned_data.get('link')
                if link is not None:
                    product_image.product_id = self.object.id
                    product_image.link = link
                    product_image.save()
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(product_form=product_form, image_form=image_form))


class OrderListView(LoginRequiredMixin, ListView):
    """Все заказы для администратора"""
    model = Order
    template_name = 'admin_app/orders_list.html'
    context_object_name = 'order_list'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class OrderDetail(LoginRequiredMixin, FormView, UpdateView):
    """Детали заказа"""
    model = Order
    template_name = 'admin_app/order_detail.html'
    success_url = reverse_lazy('admin_app:orders_list')
    context_object_name = 'orders'
    form_class = OrderListForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object = Order.objects.get(id=self.kwargs.get('pk'))
        context['order'] = OrderItem.objects.filter(order_id=self.kwargs.get('pk'))
        context['product'] = Product.objects.all()
        context['form'] = OrderListForm(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        self.object = Order.objects.get(id=self.kwargs.get('pk'))
        form = OrderListForm(request.POST)
        if form.is_valid():
            self.object.order_status = form.cleaned_data['order_status']
            self.object.save()
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data())


@login_required
def order_detail(request, pk):
    """Детали заказа"""
    if request.user.is_superuser:
        order_items = OrderItem.objects.filter(order_id=pk)
        order = Order.objects.get(id=pk)
        product = Product.objects.all()
        if request.method == 'POST':
            form = OrderListForm(request.POST, initial={'order_status': order.order_status})
            if form.is_valid():
                order.order_status = form.cleaned_data['order_status']
                order.save()
            return redirect('admin_app:orders_list')
        else:
            form = OrderListForm(initial={'order_status': order.order_status})
        return render(request, 'admin_app/order_detail.html', {'order': order_items, 'form': form, 'product': product})
    else:
        return redirect('shop:title')


class ProductAdminDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    template_name = 'admin_app/delete_product.html'
    success_url = reverse_lazy('admin_app:all_product')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class Chats(LoginRequiredMixin, ListView):
    """Активные чаты"""
    model = ChatDialog
    queryset = ChatDialog.objects.filter(is_active=True)
    template_name = 'admin_app/chats.html'
    context_object_name = "chats"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


def stocks(request):
    """Акции"""
    if request.method == 'POST':
        form = StocksForm(request.POST)
        if form.is_valid():
            stock = form.cleaned_data['title']
            phones = User.objects.values('phone')
            phone_list = []
            for phone in phones:
                phone_list.append(phone['phone'])
            send_for_users_phone.delay(phone_list, stock)
            return redirect('admin_app:all_product')
    else:
        form = StocksForm()
        return render(request, 'admin_app/stocks.html', {'form': form})
