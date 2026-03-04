from django.contrib import admin
from .models import Scan, ThermographicFeature, AIPrediction, ExplainabilityMap, FootRegionAnalysis


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display  = ('id', 'patient_name', 'patient_id', 'patient_age', 'source', 'created_at')
    list_filter   = ('source', 'created_at')
    search_fields = ('patient_name', 'patient_id')
    ordering      = ('-created_at',)


@admin.register(AIPrediction)
class AIPredictionAdmin(admin.ModelAdmin):
    list_display  = ('scan', 'diagnosis', 'confidence', 'risk_level', 'predicted_at')
    list_filter   = ('diagnosis', 'risk_level')
    ordering      = ('-predicted_at',)


@admin.register(ThermographicFeature)
class ThermographicFeatureAdmin(admin.ModelAdmin):
    list_display = ('scan', 'left_mean', 'right_mean', 'delta_mean', 'asymmetry_max')


@admin.register(FootRegionAnalysis)
class FootRegionAnalysisAdmin(admin.ModelAdmin):
    list_display = ('scan', 'side', 'region', 'mean_temp', 'delta_temp')
    list_filter  = ('side', 'region')


@admin.register(ExplainabilityMap)
class ExplainabilityMapAdmin(admin.ModelAdmin):
    list_display = ('scan',)