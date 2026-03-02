"""
URL configuration for Credit Approval System.
"""
from django.urls import path, include

urlpatterns = [
    path("", include("core.urls")),
]
