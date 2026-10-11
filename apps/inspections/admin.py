from django.contrib import admin

from .models import ChecklistItem, Inspection, InspectionResult


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("store", "scheduled_for", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("store__name",)
    autocomplete_fields = ("store",)


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "ordering", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "title")
    ordering = ("ordering", "code")


@admin.register(InspectionResult)
class InspectionResultAdmin(admin.ModelAdmin):
    list_display = ("inspection", "checklist_item", "outcome", "created_at")
    list_filter = ("outcome", "created_at")
    search_fields = ("checklist_item__code", "inspection__store__name")
    autocomplete_fields = ("inspection", "checklist_item")
