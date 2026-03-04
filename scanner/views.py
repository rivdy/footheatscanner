"""
views.py — Scanner App
Flow: Upload PNG + CSV kiri & kanan → Prediksi → Tampilkan hasil
"""

import os
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages

from .models import Scan, ThermographicFeature, AIPrediction, ExplainabilityMap
from .ml_model import predict_diagnosis, generate_attention_map, load_thermal_csv


# ───────────────────────────────────────────
# LANDING PAGE
# ───────────────────────────────────────────
def landing(request):
    latest_scan = Scan.objects.select_related('prediction').order_by('-created_at').first()
    total_scans = Scan.objects.count()
    return render(request, 'scanner/landing.html', {
        'latest_scan': latest_scan,
        'total_scans': total_scans,
    })


# ───────────────────────────────────────────
# SCANNER PAGE (form upload)
# ───────────────────────────────────────────
def scanner_view(request):
    if request.method == "GET":
        return render(request, "scanner/scanner.html")

    # ── Validasi file yang diupload ──────────────────────
    required = {
        "png_left":  "Gambar thermal kaki kiri (.png/.jpg)",
        "csv_left":  "Data suhu kaki kiri (.csv)",
        "png_right": "Gambar thermal kaki kanan (.png/.jpg)",
        "csv_right": "Data suhu kaki kanan (.csv)",
    }
    for field, label in required.items():
        if field not in request.FILES:
            messages.error(request, f"File belum diupload: {label}")
            return render(request, "scanner/scanner.html")

    # ── Baca data pasien ─────────────────────────────────
    patient_name = request.POST.get("patient_name", "Unknown").strip()
    patient_age  = request.POST.get("patient_age", None)
    patient_id   = request.POST.get("patient_id", str(uuid.uuid4())[:8]).strip()

    # ── Buat objek Scan ──────────────────────────────────
    scan = Scan.objects.create(
        patient_name=patient_name,
        patient_age=int(patient_age) if patient_age and patient_age.isdigit() else None,
        patient_id=patient_id,
        source='upload',
        image_left=request.FILES['png_left'],
        image_right=request.FILES['png_right'],
        csv_left=request.FILES['csv_left'],
        csv_right=request.FILES['csv_right'],
    )

    # ── Path absolut file yang tersimpan ────────────────
    csv_left_path  = os.path.join(settings.MEDIA_ROOT, scan.csv_left.name)
    csv_right_path = os.path.join(settings.MEDIA_ROOT, scan.csv_right.name)
    png_left_path  = os.path.join(settings.MEDIA_ROOT, scan.image_left.name)
    png_right_path = os.path.join(settings.MEDIA_ROOT, scan.image_right.name)

    # ── Jalankan prediksi ML ─────────────────────────────
    try:
        result = predict_diagnosis(csv_left_path, csv_right_path)
    except Exception as e:
        scan.delete()
        messages.error(request, f"Gagal menganalisis scan: {e}")
        return render(request, "scanner/scanner.html")

    # ── Simpan hasil ke database ─────────────────────────
    feat = result["features"]
    ThermographicFeature.objects.create(
        scan=scan,
        left_mean=feat["left_mean"],
        right_mean=feat["right_mean"],
        left_max=0,   # bisa dikembangkan nanti
        right_max=0,
        left_min=0,
        right_min=0,
        delta_mean=feat["delta_mean"],
        symmetry_index=feat["symmetry_index"],
        asymmetry_max=feat["asymmetry_max"],
    )

    prob = result["probabilities"]
    AIPrediction.objects.create(
        scan=scan,
        diagnosis=result["diagnosis"],
        confidence=result["confidence"],
        risk_level=result["risk_level"],
        prob_dm=prob.get("DM", 0),
        prob_dpn=prob.get("DPN", 0),
        prob_pad=prob.get("PAD", 0),
        model_version='rule-based-v1',
    )

    # ── Generate heatmap ─────────────────────────────────
    try:
        heatmap_dir = os.path.join(settings.MEDIA_ROOT, "heatmaps")
        os.makedirs(heatmap_dir, exist_ok=True)

        heatmap_left_rel  = f"heatmaps/{scan.id}_left.png"
        heatmap_right_rel = f"heatmaps/{scan.id}_right.png"

        left_matrix  = load_thermal_csv(csv_left_path)
        right_matrix = load_thermal_csv(csv_right_path)

        generate_attention_map(left_matrix,  os.path.join(settings.MEDIA_ROOT, heatmap_left_rel))
        generate_attention_map(right_matrix, os.path.join(settings.MEDIA_ROOT, heatmap_right_rel))

        ExplainabilityMap.objects.create(
            scan=scan,
            heatmap_left=heatmap_left_rel,
            heatmap_right=heatmap_right_rel,
        )
    except Exception as e:
        # Heatmap gagal bukan error fatal, lanjutkan
        print(f"[WARNING] Heatmap gagal dibuat: {e}")

    return redirect("results", scan_id=scan.id)


# ───────────────────────────────────────────
# RESULT PAGE
# ───────────────────────────────────────────
def results(request, scan_id):
    scan = get_object_or_404(
        Scan.objects.select_related('prediction', 'features', 'explainability'),
        id=scan_id
    )

    prediction   = getattr(scan, 'prediction',     None)
    features     = getattr(scan, 'features',       None)
    explainability = getattr(scan, 'explainability', None)

    return render(request, 'scanner/result.html', {
        'scan':          scan,
        'prediction':    prediction,
        'features':      features,
        'explainability': explainability,
    })
