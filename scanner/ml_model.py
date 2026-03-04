"""
ml_model.py
Thermal Foot Scanner — ML & Feature Engineering
Klasifikasi: DM / DPN / PAD / Normal
"""

import csv
import os
import numpy as np

# cv2 opsional, fallback ke matplotlib
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


# ───────────────────────────────────────────
# KONFIGURASI
# ───────────────────────────────────────────
LABEL_MAP = {
    0: "Normal",
    1: "DM",
    2: "DPN",
    3: "PAD",
}

ZONE_NAMES = ["toe", "forefoot", "midfoot", "heel"]


# ───────────────────────────────────────────
# 1. LOAD CSV  (fix: handle ragged rows)
# ───────────────────────────────────────────
def load_thermal_csv(csv_path: str) -> np.ndarray:
    """
    Load CSV matriks suhu ke numpy array.
    Baris dengan panjang berbeda di-pad dengan 0 (background).
    Nilai 0 = area di luar kaki (bukan suhu nol sebenarnya).
    """
    rows = []
    max_cols = 0

    with open(csv_path, "r") as f:
        for line in csv.reader(f):
            row = []
            for val in line:
                val = val.strip()
                row.append(float(val) if val else 0.0)
            rows.append(row)
            max_cols = max(max_cols, len(row))

    # Pad tiap baris supaya sama panjang
    padded = [r + [0.0] * (max_cols - len(r)) for r in rows]
    return np.array(padded, dtype=np.float32)


# ───────────────────────────────────────────
# 2. EKSTRAKSI FITUR PER ZONA
# ───────────────────────────────────────────
def _zone_stats(arr: np.ndarray) -> dict:
    """
    Hitung statistik suhu per zona anatomis vertikal.
    Kaki dibagi 4 zona: toe (atas) → heel (bawah).
    Nilai 0 diabaikan (background).
    """
    h = arr.shape[0]
    zone_h = h // 4
    stats = {}

    for i, name in enumerate(ZONE_NAMES):
        zone = arr[i * zone_h: (i + 1) * zone_h]
        pixels = zone[zone > 0]

        if len(pixels) == 0:
            stats[name] = {"mean": 0, "max": 0, "min": 0, "std": 0}
        else:
            stats[name] = {
                "mean": float(pixels.mean()),
                "max":  float(pixels.max()),
                "min":  float(pixels.min()),
                "std":  float(pixels.std()),
            }

    return stats


def compute_features(left_matrix: np.ndarray, right_matrix: np.ndarray) -> dict:
    """
    Gabungkan fitur dari kaki kiri dan kanan.
    Fitur utama:
      - Rata-rata & std suhu tiap kaki
      - Asimetri (selisih L vs R) per zona
      - Symmetry Index (SI): indikator klinis DPN
      - Skor PAD: kaki dingin secara absolut
    """
    left_pixels  = left_matrix[left_matrix > 0]
    right_pixels = right_matrix[right_matrix > 0]

    left_mean  = float(left_pixels.mean())  if len(left_pixels)  else 0
    right_mean = float(right_pixels.mean()) if len(right_pixels) else 0
    left_max   = float(left_pixels.max())   if len(left_pixels)  else 0
    right_max  = float(right_pixels.max())  if len(right_pixels) else 0
    left_min   = float(left_pixels.min())   if len(left_pixels)  else 0
    right_min  = float(right_pixels.min())  if len(right_pixels) else 0

    delta_mean     = abs(left_mean - right_mean)
    avg_mean       = (left_mean + right_mean) / 2 if (left_mean + right_mean) > 0 else 1
    symmetry_index = delta_mean / avg_mean

    # Asimetri per zona
    left_zones  = _zone_stats(left_matrix)
    right_zones = _zone_stats(right_matrix)
    zone_asymmetry = {}
    for zone in ZONE_NAMES:
        zone_asymmetry[zone] = abs(left_zones[zone]["mean"] - right_zones[zone]["mean"])

    asymmetry_max = max(zone_asymmetry.values())

    return {
        "left_mean":       left_mean,
        "right_mean":      right_mean,
        "left_max":        left_max,
        "right_max":       right_max,
        "left_min":        left_min,
        "right_min":       right_min,
        "delta_mean":      delta_mean,
        "symmetry_index":  symmetry_index,
        "asymmetry_max":   asymmetry_max,
        "zone_asymmetry":  zone_asymmetry,
        "left_zones":      left_zones,
        "right_zones":     right_zones,
    }


# ───────────────────────────────────────────
# 3. RULE-BASED SCORING  (DM / DPN / PAD)
# ───────────────────────────────────────────
def compute_pad_dpn_score(features: dict) -> tuple:
    """
    Scoring berbasis aturan klinis thermal foot:

    PAD  → suhu absolut rendah (kaki dingin)
           avg_mean < 28°C → indikasi aliran darah buruk
    DPN  → asimetri tinggi antara L dan R
           symmetry_index > 0.04 atau asymmetry_max > 1°C
    DM   → kedua indikator moderat
    Normal → semua dalam batas normal

    Returns:
        diagnosis (str), pad_score (float), dpn_score (float)
    """
    avg_mean       = (features["left_mean"] + features["right_mean"]) / 2
    symmetry_index = features["symmetry_index"]
    asymmetry_max  = features["asymmetry_max"]

    # Skor 0–10
    # PAD: makin dingin → makin tinggi
    pad_score = max(0, min(10, (32 - avg_mean) * 0.8))

    # DPN: makin asimetri → makin tinggi
    dpn_score = min(10, symmetry_index * 80 + asymmetry_max * 2)

    # Tentukan diagnosis
    if pad_score >= 6 and pad_score > dpn_score:
        diagnosis = "PAD"
    elif dpn_score >= 5 and dpn_score > pad_score:
        diagnosis = "DPN"
    elif pad_score >= 3 or dpn_score >= 3:
        diagnosis = "DM"
    else:
        diagnosis = "Normal"

    # Risk level
    combined = (pad_score + dpn_score) / 2
    if combined >= 6:
        risk_level = "High"
    elif combined >= 3:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    # Probabilitas kasar untuk ditampilkan di UI
    total = pad_score + dpn_score + 0.5
    probabilities = {
        "DM":     round(min(100, (pad_score + dpn_score) * 3), 1),
        "DPN":    round(min(100, dpn_score * 10), 1),
        "PAD":    round(min(100, pad_score * 10), 1),
        "Normal": round(max(0, 100 - (pad_score + dpn_score) * 5), 1),
    }

    return diagnosis, round(pad_score, 2), round(dpn_score, 2), risk_level, probabilities


# ───────────────────────────────────────────
# 4. FUNGSI PREDIKSI UTAMA (dipanggil views.py)
# ───────────────────────────────────────────
def predict_diagnosis(csv_left: str, csv_right: str) -> dict:
    """
    Pipeline lengkap: load CSV → fitur → scoring → hasil.

    Args:
        csv_left:  path absolut ke file CSV kaki kiri
        csv_right: path absolut ke file CSV kaki kanan

    Returns:
        {
            "diagnosis": "DPN",
            "confidence": 78.5,
            "risk_level": "Moderate",
            "pad_score": 3.2,
            "dpn_score": 5.8,
            "probabilities": {"DM": ..., "DPN": ..., "PAD": ..., "Normal": ...},
            "features": { ... }
        }
    """
    left_matrix  = load_thermal_csv(csv_left)
    right_matrix = load_thermal_csv(csv_right)

    features = compute_features(left_matrix, right_matrix)
    diagnosis, pad_score, dpn_score, risk_level, probabilities = compute_pad_dpn_score(features)

    # Confidence = probabilitas kelas yang diprediksi
    confidence = probabilities.get(diagnosis, 0.0)

    return {
        "diagnosis":     diagnosis,
        "confidence":    confidence,
        "risk_level":    risk_level,
        "pad_score":     pad_score,
        "dpn_score":     dpn_score,
        "probabilities": probabilities,
        "features": {
            "left_mean":      round(features["left_mean"], 2),
            "right_mean":     round(features["right_mean"], 2),
            "delta_mean":     round(features["delta_mean"], 2),
            "symmetry_index": round(features["symmetry_index"], 4),
            "asymmetry_max":  round(features["asymmetry_max"], 2),
        },
    }


# ───────────────────────────────────────────
# 5. ATTENTION MAP / HEATMAP OVERLAY
# ───────────────────────────────────────────
def generate_attention_map(thermal_matrix: np.ndarray, save_path: str) -> str:
    """
    Buat heatmap berwarna dari matriks suhu.
    Background (nilai 0) dibuat transparan/hitam.

    Args:
        thermal_matrix: 2D numpy array hasil load_thermal_csv
        save_path:      path output gambar PNG

    Returns:
        save_path
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Normalisasi hanya piksel kaki (nilai > 0)
    mask = thermal_matrix > 0
    normalized = np.zeros_like(thermal_matrix, dtype=np.float32)

    if mask.any():
        vmin = thermal_matrix[mask].min()
        vmax = thermal_matrix[mask].max()
        if vmax > vmin:
            normalized[mask] = (thermal_matrix[mask] - vmin) / (vmax - vmin)
        else:
            normalized[mask] = 0.5

    heatmap_uint8 = np.uint8(255 * normalized)

    if CV2_AVAILABLE:
        heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
        # Buat background hitam (bukan kaki)
        heatmap_color[~mask] = [0, 0, 0]
        cv2.imwrite(save_path, heatmap_color)
    else:
        import matplotlib.pyplot as plt
        display = np.ma.masked_where(~mask, normalized)
        fig, ax = plt.subplots(figsize=(4, 6))
        ax.imshow(display, cmap="jet", vmin=0, vmax=1)
        ax.axis("off")
        fig.savefig(save_path, bbox_inches="tight", pad_inches=0, dpi=100)
        plt.close(fig)

    return save_path