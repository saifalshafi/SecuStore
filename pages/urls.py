"""URL configuration for the pages app.

All paths are mounted at the site root ``/`` by the root URL conf.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('features/', views.features, name='features'),
    path('navbar/', views.navbar_view, name='navbar'),
    path('intro/', views.intro, name='intro'),
]
