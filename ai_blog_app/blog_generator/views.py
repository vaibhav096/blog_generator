from django.shortcuts import render,redirect
from django.contrib.auth.models import User
from django.contrib.auth import login,logout,authenticate
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    return render(request,'index.html')


def generate_blog(request):
    pass



def user_login(request):
    if request.method =='POST':
        username=request.POST['username']
        password=request.POST['password']

        user=authenticate(request,username=username,password=password)

        if user is not None:
            login(request,user)
            return redirect('/')
        else:
            error_message="Invalid username or password"
            return render(request, 'login.html',{'error_message':error_message})

    return render(request, 'login.html')


def user_signup(request):
    if request.method =='POST':
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password']
        repeatPassword=request.POST['repeatPassword']

        if password==repeatPassword:
            try:
                user=User.objects.create_user(username,email,password)
                user.save()
                login(request,user)
                return redirect('/')
            except:
                error_message="Error occured ,make unique entries"    
                return render(request,'signup.html',{'error_message': error_message})

        else:
            error_message ="password does not match"
            return render(request,'signup.html',{'error_message': error_message})
    return render(request, 'signup.html')



def user_logout(request):
    logout(request)
    return redirect('/')


# Create your views here.
