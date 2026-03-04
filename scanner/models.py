from django.db import models


class Scan(models.Model):
    """
    Menyimpan satu sesi scan pasien (sepasang kaki kiri + kanan).
    """
    SOURCE_CHOICES = [
        ('upload', 'Upload Manual'),
        ('device', 'Thermal Device'),
    ]

    patient_name    = models.CharField(max_length=100, default='Unknown')
    patient_age     = models.PositiveIntegerField(null=True, blank=True)
    patient_id      = models.CharField(max_length=50, blank=True)
    source          = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='upload')

    # File gambar thermal (PNG)
    image_left      = models.ImageField(upload_to='scans/', null=True, blank=True)
    image_right     = models.ImageField(upload_to='scans/', null=True, blank=True)

    # File data suhu (CSV)
    csv_left        = models.FileField(upload_to='scans/', null=True, blank=True)
    csv_right       = models.FileField(upload_to='scans/', null=True, blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Scan #{self.id} — {self.patient_name} ({self.created_at.strftime('%d %b %Y')})"


class ThermographicFeature(models.Model):
    """
    Fitur statistik suhu yang diekstrak dari CSV kiri dan kanan.
    """
    scan                    = models.OneToOneField(Scan, on_delete=models.CASCADE, related_name='features')

    left_mean               = models.FloatField(default=0)
    left_max                = models.FloatField(default=0)
    left_min                = models.FloatField(default=0)

    right_mean              = models.FloatField(default=0)
    right_max               = models.FloatField(default=0)
    right_min               = models.FloatField(default=0)

    delta_mean              = models.FloatField(default=0)   # selisih rata-rata L vs R
    symmetry_index          = models.FloatField(default=0)   # indeks asimetri (0–1)
    asymmetry_max           = models.FloatField(default=0)   # asimetri maksimum antar zona

    def __str__(self):
        return f"Features — Scan #{self.scan_id}"


class FootRegionAnalysis(models.Model):
    """
    Analisis suhu per zona anatomis kaki (toe, forefoot, midfoot, heel).
    """
    REGION_CHOICES = [
        ('toe',       'Toe / Jari'),
        ('forefoot',  'Forefoot / Depan'),
        ('midfoot',   'Midfoot / Tengah'),
        ('heel',      'Heel / Tumit'),
    ]
    SIDE_CHOICES = [
        ('left',  'Kiri'),
        ('right', 'Kanan'),
    ]

    scan        = models.ForeignKey(Scan, on_delete=models.CASCADE, related_name='region_analyses')
    region      = models.CharField(max_length=10, choices=REGION_CHOICES)
    side        = models.CharField(max_length=5, choices=SIDE_CHOICES)
    mean_temp   = models.FloatField(default=0)
    max_temp    = models.FloatField(default=0)
    delta_temp  = models.FloatField(default=0)   # selisih L vs R pada zona ini

    def __str__(self):
        return f"{self.get_side_display()} {self.get_region_display()} — Scan #{self.scan_id}"


class AIPrediction(models.Model):
    """
    Hasil prediksi model ML untuk satu scan.
    """
    DIAGNOSIS_CHOICES = [
        ('DM',     'Diabetes Mellitus'),
        ('DPN',    'Diabetic Peripheral Neuropathy'),
        ('PAD',    'Peripheral Arterial Disease'),
        ('Normal', 'Normal'),
    ]
    RISK_CHOICES = [
        ('Low',      'Rendah'),
        ('Moderate', 'Sedang'),
        ('High',     'Tinggi'),
    ]

    scan            = models.OneToOneField(Scan, on_delete=models.CASCADE, related_name='prediction')
    diagnosis       = models.CharField(max_length=20, choices=DIAGNOSIS_CHOICES)
    confidence      = models.FloatField(default=0)          # persentase 0–100
    risk_level      = models.CharField(max_length=10, choices=RISK_CHOICES, default='Low')
    prob_dm         = models.FloatField(default=0)
    prob_dpn        = models.FloatField(default=0)
    prob_pad        = models.FloatField(default=0)
    model_version   = models.CharField(max_length=50, default='rule-based-v1')
    predicted_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.diagnosis} ({self.confidence:.1f}%) — Scan #{self.scan_id}"


class ExplainabilityMap(models.Model):
    """
    Heatmap overlay untuk visualisasi area berisiko.
    """
    scan            = models.OneToOneField(Scan, on_delete=models.CASCADE, related_name='explainability')
    heatmap_left    = models.ImageField(upload_to='heatmaps/', null=True, blank=True)
    heatmap_right   = models.ImageField(upload_to='heatmaps/', null=True, blank=True)
    overlay_left    = models.ImageField(upload_to='overlays/', null=True, blank=True)
    overlay_right   = models.ImageField(upload_to='overlays/', null=True, blank=True)

    def __str__(self):
        return f"Heatmap — Scan #{self.scan_id}"