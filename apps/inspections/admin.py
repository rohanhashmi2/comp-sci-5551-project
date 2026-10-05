from django.contrib import admin

from .models import Inspection


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("store", "scheduled_for", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("store__name",)
    autocomplete_fields = ("store",)
