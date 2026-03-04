"""
services.py — Business logic layer
Wrapper tipis antara views.py dan ml_model.py
"""

from .ml_model import predict_diagnosis as _predict, generate_attention_map, load_thermal_csv


def generate_diagnosis(csv_left: str, csv_right: str) -> dict:
    """
    Jalankan analisis thermal dan kembalikan hasil lengkap.

    Args:
        csv_left:  path absolut ke CSV kaki kiri
        csv_right: path absolut ke CSV kaki kanan

    Returns:
        dict hasil dari ml_model.predict_diagnosis()
        {
            "diagnosis", "confidence", "risk_level",
            "pad_score", "dpn_score", "probabilities", "features"
        }
    """
    return _predict(csv_left, csv_right)


def build_heatmaps(scan, media_root: str) -> dict:
    """
    Generate heatmap PNG untuk kaki kiri dan kanan.

    Args:
        scan:       objek Scan (dari models.py)
        media_root: settings.MEDIA_ROOT

    Returns:
        {"left": "heatmaps/X_left.png", "right": "heatmaps/X_right.png"}
        atau {} jika gagal
    """
    import os

    try:
        left_matrix  = load_thermal_csv(os.path.join(media_root, scan.csv_left.name))
        right_matrix = load_thermal_csv(os.path.join(media_root, scan.csv_right.name))

        left_rel  = f"heatmaps/{scan.id}_left.png"
        right_rel = f"heatmaps/{scan.id}_right.png"

        os.makedirs(os.path.join(media_root, "heatmaps"), exist_ok=True)

        generate_attention_map(left_matrix,  os.path.join(media_root, left_rel))
        generate_attention_map(right_matrix, os.path.join(media_root, right_rel))

        return {"left": left_rel, "right": right_rel}

    except Exception as e:
        print(f"[WARNING] build_heatmaps gagal: {e}")
        return {}