from django.urls import path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('lista/', views.objectList, name='list'),
    path('sobre/', views.about, name='about'),
    path('guia/', views.tutorial, name='tutorial'),
    path('teoria/', views.theory, name='theory'),
    path('lista/observacoes', views.modal, name='modal'),
    path('objeto/<int:ticID>/<int:ind>', views.tessObject, name='object'),
    path('objeto/to_periodogram/<int:ticID>/<int:ind>', views.foldLightCurve, name='folded'),
    path('objeto/processar/<int:ticID>/<int:ind>', views.process_lightcurve, name='lc_process'),
]

urlpatterns += staticfiles_urlpatterns()
