from django.urls import path
from . import views

urlpatterns = [
    path("",                  views.landing,      name="landing"),
    path("scan/",             views.scanner_view, name="scanner"),
    path("results/<int:scan_id>/", views.results, name="results"),
]