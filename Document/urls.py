from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('documents/', views.document_list, name='document_list'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/new/', views.document_create, name='document_create'),
    path('documents/edit/<int:pk>/', views.document_update, name='document_update'),
    path('documents/delete/<int:pk>/', views.document_delete, name='document_delete'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
