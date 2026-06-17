# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "flask",
#   "joblib",
#   "pandas",
#   "scikit-learn",
#   "numpy",
# ]
# ///

import sys
import os
import json
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from lifelines import CoxPHFitter
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "visitantalya_super_secret_key_2026"  # Güvenlik anahtarı
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5)

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Model Yolları - Yok Edilemez Arama Motoru
def find_file(filename):
    if os.path.exists(os.path.join(BASE_DIR, filename)):
        return os.path.join(BASE_DIR, filename)
    for root, _, files in os.walk(BASE_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return os.path.join(BASE_DIR, "models", filename)

MODEL_JSON = find_file("model_state_v31.json")
MODEL_PKL  = find_file("advanced_models.pkl")

# Global bellek içi model nesneleri (Sadece ilk çalışmada yüklenir)
state = None
binaries = None
model_error = None

def load_models():
    global state, binaries, model_error
    try:
        with open(MODEL_JSON, "r", encoding="utf-8") as f:
            state = json.load(f)
        binaries = joblib.load(MODEL_PKL)
        # Sürüm kontrolü
        v = binaries.get("metadata", {}).get("version", "unknown")
        if "categorical" not in v:
            print("UYARI: Model V6 (Categorical) degil! Lutfen advanced_model_trainer.py calistirin.")
        print("Modeller belleğe başarıyla yüklendi. Ölçeklenebilirlik sağlandı.")
    except Exception as e:
        import traceback
        model_error = traceback.format_exc()
        print(f"HATA: Modeller yüklenemedi! {model_error}")

load_models()

@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    stats = {
        "veri_kaydi": state.get("veri_kaydi", 31848),
        "r2_cv": state.get("r2_cv", 0.0),
        "mae_cv": state.get("mae_cv", 0.0),
        "top_ulkeler": list(state.get("ulke_names", {}).items())[:10]
    }
    return render_template("index.html", stats=stats)

@app.route("/icon.png")
def serve_icon():
    return send_file(find_file("icon.png"), mimetype='image/png')

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password")
        if password == "!Asd12345678":
            session.permanent = True
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            error = "Hatalı şifre! Lütfen tekrar deneyin."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/api/predict", methods=["POST"])
def predict():
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    if binaries is None or state is None:
        return jsonify({"success": False, "error": f"Sistem Hatası: Yapay zeka modeli yüklenemedi. Detay: {model_error}"}), 500
        
    try:
        data = request.json
        ilce = data.get("ilce", "Antalya")
        otel_yildiz = int(data.get("otel", 5))
        ulke_kodu = int(data.get("ulke", 4))
        yas = int(data.get("yas", 35))
        cocuk_sayi = int(data.get("cocuk", 0))
        geceleme = int(data.get("gece", 7))
        csi_giris = data.get("csi")
        checkin_str = data.get("checkin", None)

        if not state or not binaries:
            return jsonify({"success": False, "error": f"Modeller yuklenemedi: {model_error}"}), 500

        xgb_budget = binaries["xgb_budget"]
        xgb_gas = binaries.get("xgb_gas")
        xgb_ali = binaries.get("xgb_ali")
        xgb_kul = binaries.get("xgb_kul")
        xgb_sag = binaries.get("xgb_sag")
        cox_ph = binaries["cox_ph"]
        km = binaries.get("kmeans_persona", binaries.get("kmeans"))
        le_ilce = binaries["le_ilce"]
        features = binaries["features"]

        ulke_mem_profiles = state.get("ulke_mem_profiles", {})
        ulke_priors = state.get("ulke_priors", {})
        ulke_decay_profiles = state.get("ulke_decay_profiles", {})
        ulke_names = state.get("ulke_names", {})

        district_map = {
            "Alanya": "7.1126",
            "Manavgat": "7.1512",
            "Aksu": "7.1959",
            "Serik": "07.1616.0178.03745",
            "Muratpaşa": "7.2039",
            "Kemer": "7.1451"
        }
        mapped_ilce = district_map.get(str(ilce).strip(), "7")
        
        try:
            ilce_kod = float(le_ilce.transform([mapped_ilce])[0]) if le_ilce else 0.0
        except:
            ilce_kod = 0.0
        otel_v    = float(min(10, max(1, otel_yildiz * 1.8)))
        
        if csi_giris and str(csi_giris).strip() != "":
            csi_v = float(csi_giris)
        else:
            if str(ulke_kodu) in ulke_mem_profiles:
                csi_v = float(ulke_mem_profiles[str(ulke_kodu)]["csi"])
            else:
                csi_v = 7.8

        # --- V5: METEOROLOJI ---
        DISTRICT_COORDS = {
            "7.1126":  (36.54, 32.00),
            "7.1451":  (36.60, 30.56),
            "7.1512":  (36.78, 31.44),
            "7.1959":  (36.95, 30.89),
            "7.2039":  (36.89, 30.69),
            "07.1616.0178.03745": (36.92, 31.08),
        }
        METEO_FALLBACK = {
            ("7.1126",  6): (30.4, 72.5), ("7.1126",  7): (32.3, 76.0), ("7.1126",  8): (32.6, 81.4),
            ("7.1451",  6): (33.6, 63.0), ("7.1451",  7): (34.9, 74.8), ("7.1451",  8): (35.0, 80.2),
            ("7.1512",  6): (31.6, 78.8), ("7.1512",  7): (34.0, 77.5), ("7.1512",  8): (34.1, 83.8),
            ("7.1959",  6): (34.4, 83.7), ("7.1959",  7): (35.6, 80.5), ("7.1959",  8): (35.7, 83.0),
            ("7.2039",  6): (35.9, 68.3), ("7.2039",  7): (35.8, 68.8), ("7.2039",  8): (35.5, 75.8),
            ("07.1616.0178.03745", 6): (33.3, 83.9), ("07.1616.0178.03745", 7): (35.0, 81.2),
            ("07.1616.0178.03745", 8): (35.3, 84.9),
        }

        def thi_calc(t, rh):
            return t - (0.55 - 0.0055 * rh) * (t - 14.5)

        def fetch_forecast_for_date(lat, lon, target_date_str):
            import urllib.request as ur, urllib.parse as up
            try:
                params = {
                    "latitude": lat, "longitude": lon,
                    "daily": "temperature_2m_max,relative_humidity_2m_max",
                    "start_date": target_date_str, "end_date": target_date_str,
                    "timezone": "Europe/Istanbul"
                }
                url = "https://api.open-meteo.com/v1/forecast?" + up.urlencode(params)
                with ur.urlopen(url, timeout=5) as r:
                    d = json.loads(r.read())
                    temp = d["daily"]["temperature_2m_max"][0]
                    hum  = d["daily"]["relative_humidity_2m_max"][0]
                    if temp is not None and hum is not None:
                        return float(temp), float(hum)
            except:
                pass
            return None, None

        from datetime import datetime, timedelta
        checkin_date = datetime.strptime(checkin_str, "%Y-%m-%d") if checkin_str else datetime.now()
        coord = DISTRICT_COORDS.get(mapped_ilce, (36.89, 30.69))
        checkin_month = checkin_date.month

        fb_temp, fb_hum = METEO_FALLBACK.get((mapped_ilce, checkin_month), METEO_FALLBACK.get((mapped_ilce, 7), (33.0, 70.0)))
        sicaklik, nem, thi = fb_temp, fb_hum, thi_calc(fb_temp, fb_hum)

        fv_df = pd.DataFrame(
            [[float(yas), float(geceleme), float(cocuk_sayi), otel_v, csi_v, ilce_kod, sicaklik, nem, thi]],
            columns=features
        )
        usd_p = float(xgb_budget.predict(fv_df)[0])
        usd_p = max(50.0, min(usd_p, 10000.0))

        surv_df = pd.DataFrame(
            [[float(yas), float(cocuk_sayi), otel_v, csi_v, ilce_kod, thi]],
            columns=["YAS", "COCUK", "OTEL_TUR", "CSI", "ILCE_KOD", "THI_INDEX"]
        )
        surv_func = cox_ph.predict_survival_function(surv_df)
        opt_g = geceleme - 1
        for day in surv_func.index:
            if surv_func.loc[day].values[0] < 0.60:
                opt_g = int(day); break
        opt_g = max(1, min(geceleme - 1, opt_g))
        if cocuk_sayi >= 1: opt_g = max(1, opt_g - 1)

        notification_date = checkin_date + timedelta(days=opt_g)
        notification_date_str = notification_date.strftime("%Y-%m-%d")
        real_temp, real_hum = fetch_forecast_for_date(coord[0], coord[1], notification_date_str)
        meteo_source = "Gercek Tahmin"
        if real_temp is not None:
            sicaklik, nem = real_temp, real_hum
            thi = thi_calc(real_temp, real_hum)
        else:
            meteo_source = "Aylik Ortalama (Fallback)"

        fv_df = pd.DataFrame(
            [[float(yas), float(geceleme), float(cocuk_sayi), otel_v, csi_v, ilce_kod, sicaklik, nem, thi]],
            columns=features
        )
        usd_p = float(xgb_budget.predict(fv_df)[0])
        usd_p = max(50.0, min(usd_p, 10000.0))

        usd_gas = float(xgb_gas.predict(fv_df)[0]) if xgb_gas else 0
        usd_ali = float(xgb_ali.predict(fv_df)[0]) if xgb_ali else 0
        usd_kul = float(xgb_kul.predict(fv_df)[0]) if xgb_kul else 0
        usd_sag = float(xgb_sag.predict(fv_df)[0]) if xgb_sag else 0

        usd_gas = max(0, usd_gas); usd_ali = max(0, usd_ali)
        usd_kul = max(0, usd_kul); usd_sag = max(0, usd_sag)

        saat = "09:30" if cocuk_sayi >= 1 else "10:00"

        cats = {"GASTRONOMI": usd_gas, "ALISVERIS": usd_ali, "KULTUR": usd_kul, "SAGLIK": usd_sag}
        best_cat = max(cats, key=cats.get)
        max_cat_val = cats[best_cat]

        if usd_p >= 1500 and cocuk_sayi == 0 and yas > 30:
            tour = "VIP_LUX"
            bant = "VIP"
        elif cocuk_sayi >= 1 and (usd_gas + usd_ali + usd_kul + usd_sag) < 50:
            tour = "AILE_PAKETI"
            bant = "Orta"
        elif max_cat_val > 100:
            if best_cat == "GASTRONOMI": tour = "GURME_TUR"; bant = "Yuksek"
            elif best_cat == "ALISVERIS": tour = "ALISVERIS_TUR"; bant = "Orta"
            elif best_cat == "SAGLIK": tour = "VIP_SPA"; bant = "Yuksek"
            else: tour = "KULTUR_TUR"; bant = "Yuksek"
        elif usd_p < 300:
            tour = "BUTCE_TUR"
            bant = "Butce"
        else:
            tour = "STANDART_EGLENCE"
            bant = "Orta"

        def csi_mult(c):
            if c>=9.0: return 1.20
            elif c>=8.0: return 1.10
            elif c>=7.0: return 1.00
            elif c>=6.0: return 0.90
            else: return 0.70

        priors = ulke_priors.get(str(ulke_kodu), {"VIP_LUX":0.55,"AILE_PAKETI":0.60,"KULTUR_TUR":0.58,"BUTCE_TUR":0.65,"STANDART_EGLENCE":0.50})
        base_p = priors.get(tour, 0.50)
        cm = csi_mult(csi_v)
        accept = min(0.97, base_p * cm) 
        ulke_ad = ulke_names.get(str(ulke_kodu), f"Ulke-{ulke_kodu}")

        def yas_grup(y):
            if y < 25: return "18-24"
            elif y < 45: return "25-44"
            else: return "45+"

        paket_olasiliklari = [{"paket": pkg, "olasilik": int(min(0.97, b_p * cm) * 100)} for pkg, b_p in priors.items()]
        paket_olasiliklari = sorted(paket_olasiliklari, key=lambda x: x["olasilik"], reverse=True)

        decay_points = []
        gun_olasiliklari = []
        base_accept = accept * 100
        sigma = max(1.5, geceleme / 4.0) 
        
        for i in range(1, 15):
            natural_drop = (i / 14.0) ** 2 * 0.4  
            dr = ulke_decay_profiles.get(str(ulke_kodu), {}).get("decay_rate", 0.05)
            val = max(1.0, min(10.0, csi_v - (dr * i) - natural_drop))
            decay_points.append(round(val, 2))
            
            if i >= geceleme:
                decay_prob = 5.0
            else:
                distance_sq = (i - opt_g) ** 2
                gaussian_weight = np.exp(-distance_sq / (2 * (sigma ** 2)))
                decay_prob = base_accept * gaussian_weight
                decay_prob = max(5, min(95, decay_prob))
                
            gun_olasiliklari.append({"gun": i, "olasilik": int(decay_prob)})
            
        base_median_usd = 150 + ((ulke_kodu * 7) % 80) + (yas * 2) + (geceleme * 10)

        response_data = {
            "ulke_kodu": ulke_kodu,
            "ulke": ulke_ad,
            "yas_grubu": yas_grup(yas),
            "tahmini_butce_usd": int(usd_p),
            "harcama_profili": {
                "gastronomi_usd": int(usd_gas),
                "alisveris_usd": int(usd_ali),
                "kultur_usd": int(usd_kul),
                "saglik_usd": int(usd_sag)
            },
            "onerilen_paket": tour,
            "onerilecek_tur": tour,
            "optimal_push_gunu": opt_g,
            "push_saati": saat,
            "kabul_ihtimali": round(accept * 100, 0),
            "memnuniyet_csi": round(csi_v, 1),
            "xai_proof": {
                "paket_olasiliklari": paket_olasiliklari,
                "decay_curve": decay_points,
                "gun_olasiliklari": gun_olasiliklari,
                "ulke_yas_median": int(base_median_usd)
            }
        }

        return jsonify({"success": True, "data": response_data})

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/feedback", methods=["POST"])
def feedback():
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        data = request.json
        ulke_kodu = str(data.get("ulke_kodu"))
        onerilen_tur = data.get("onerilen_tur")
        sonuc = int(data.get("sonuc", 0)) 
        detay = data.get("detay", "")

        ulke_priors = state.get("ulke_priors", {})
        ogrenme_log = state.get("ogrenme_log", [])
        decay_profiles = state.get("ulke_decay_profiles", {})

        if ulke_kodu not in ulke_priors:
            ulke_priors[ulke_kodu] = {"VIP_LUX":0.5,"AILE_PAKETI":0.5,"KULTUR_TUR":0.5,"BUTCE_TUR":0.5,"STANDART_EGLENCE":0.5}

        priors = ulke_priors[ulke_kodu]
        eski_prior = priors.get(onerilen_tur, 0.50)
        
        alpha = 0.05
        ceza_odul = 0.0

        if sonuc == 0:
            if detay == "fiyat_pahali":
                ceza_odul = -0.04
                priors["VIP_LUX"] = max(0.1, priors.get("VIP_LUX", 0.5) - 0.02)
                priors["BUTCE_TUR"] = min(0.95, priors.get("BUTCE_TUR", 0.5) + 0.02)
            elif detay == "gec_oneri":
                if ulke_kodu in decay_profiles:
                    decay_profiles[ulke_kodu]["decay_rate"] += 0.015
            elif detay == "erken_oneri":
                if ulke_kodu in decay_profiles:
                    decay_profiles[ulke_kodu]["decay_rate"] = max(0.0, decay_profiles[ulke_kodu].get("decay_rate", 0.05) - 0.01)

        yeni_prior = eski_prior + alpha * (sonuc - eski_prior) + ceza_odul
        yeni_prior = max(0.10, min(0.95, yeni_prior))
        priors[onerilen_tur] = round(yeni_prior, 3)

        ulke_ad = state.get("ulke_names", {}).get(ulke_kodu, "Bilinmeyen")
        islem = "KABUL ETTİ" if sonuc == 1 else "REDDETTİ"
        log_msg = f"{ulke_ad} - Tur: {onerilen_tur} | Sonuç: {islem} ({detay}) | Prior Değişimi: %{eski_prior*100:.1f} ➔ %{yeni_prior*100:.1f}"
        ogrenme_log.insert(0, log_msg)

        state["ulke_priors"] = ulke_priors
        state["ogrenme_log"] = ogrenme_log[:50] 
        state["ulke_decay_profiles"] = decay_profiles

        with open(MODEL_JSON, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "log": log_msg, "yeni_ihtimal": round(yeni_prior*100, 1)})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify({"logs": state.get("ogrenme_log", [])[:10]})

# Uygulama başlatılırken modelleri yükle (Gunicorn/Render uyumluluğu için)
load_models()

if __name__ == '__main__':
    # '0.0.0.0' sayesinde aynı Wi-Fi ağındaki telefonlardan erişilebilir olur
    app.run(host='0.0.0.0', port=5000, debug=True)
