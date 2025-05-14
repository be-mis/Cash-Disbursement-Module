from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import (
    CashReimbursement, Transportation, Meal, Lodging, Purchase,
    CashLiquidation, CashAdvance
)

# Define generic inlines
class TransportationInline(GenericTabularInline):
    model = Transportation
    extra = 1

class MealInline(GenericTabularInline):
    model = Meal
    extra = 1

class LodgingInline(GenericTabularInline):
    model = Lodging
    extra = 1

class PurchaseInline(GenericTabularInline):
    model = Purchase
    extra = 1

# Common Admin for Main Tables
class CommonAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'purpose', 'table_type')
    inlines = [TransportationInline, MealInline, LodgingInline, PurchaseInline]

# Register models
admin.site.register(CashAdvance, CommonAdmin)
admin.site.register(CashReimbursement, CommonAdmin)
admin.site.register(CashLiquidation, CommonAdmin)

# These are independent models, no inline needed
admin.site.register(Transportation)
admin.site.register(Meal)
admin.site.register(Lodging)
admin.site.register(Purchase)
