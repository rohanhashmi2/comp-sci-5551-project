from django.contrib import admin

from .models import Evidence, Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("__str__", "store", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "store__name")
    autocomplete_fields = ("inspection", "inspection_result", "store", "created_by")


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("ticket", "submitted_by", "review_status", "submitted_at")
    list_filter = ("review_status", "submitted_at")
    search_fields = ("ticket__title", "submitted_by__email")
    autocomplete_fields = ("ticket", "submitted_by")
