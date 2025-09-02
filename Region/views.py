from django.shortcuts import render
from django.http import HttpResponse


# Create your views here.
def list_regions(request):
    return render(request,template_name='index.html')
