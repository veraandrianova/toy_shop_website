from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import RegisterUserForm, LoginUserForm
# Create your views here.
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect

from codes.forms import CodeForm
from user.models import User


class RegisterUser(CreateView):
    form_class = RegisterUserForm
    template_name = 'user/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect('title')


class LoginUser(LoginView):
    form_class = LoginUserForm
    template_name = "user/login.html"

    def get_success_url(self):
        return reverse_lazy('title')


def logout_user(request):
    logout(request)
    return redirect('title')


@login_required
def home_view(request):
    return render(request, 'temp/main.html', {})


def auth_view(request):
    form = AuthenticationForm()
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            request.session['pk'] = user.pk
            return redirect('verify_view')
    return render(request, 'temp/auth.html', {'form': form})


def verify_view(request):
    form = CodeForm(request.POST or None)
    pk = request.session.get('pk')
    if pk:
        user = User.objects.get(pk=pk)
        code = user.code
        code_user = f'{user.username}: {user.code}'
        if not request.POST:
            print(code.user)
        if form.is_valid():
            num = form.cleaned_data.get('number')

            if str(code) == num:
                code.save()
                login(request, user)
                return redirect('home_view')
            else:
                return redirect('login_view')
    return render(request, 'temp/verify.html', {'form': form})
