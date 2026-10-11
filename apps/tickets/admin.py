from django.contrib import admin

from .models import Evidence, Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("__str__", "deadline", "issued_at")
    list_filter = ("deadline", "issued_at")
    search_fields = ("inspection__store__name",)
    autocomplete_fields = ("inspection",)


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("result", "submitted_by", "review_status", "submitted_at")
    list_filter = ("review_status", "submitted_at")
    search_fields = ("result__checklist_item__code", "submitted_by__email")
    autocomplete_fields = ("result", "submitted_by")
