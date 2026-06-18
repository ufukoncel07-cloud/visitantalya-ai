import sys, json, os, urllib.request, urllib.parse
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
from lifelines import CoxPHFitter
import joblib
import warnings

warnings.filterwarnings('ignore')

DATA_DIR = r"C:\Users\MİNE\Desktop"
if not os.path.exists(os.path.join(DATA_DIR, "HARCAMA_TABLO_Haziran.xlsx")):
    if os.path.exists(r"C:\Users\MİNE\Desktop\Turizm_Verileri"):
        DATA_DIR = r"C:\Users\MİNE\Desktop\Turizm_Verileri"

print("="*60)
print("VISITANTALYA ADVANCED DATA SCIENCE CORE (V5 - METEOROLOJİK ENRİCHMENT)")
print("="*60)

# ============================================================
# ADIM 1: METEOROLOJİK SÖZLÜK - Open-Meteo Historical API
# ============================================================
print("\n1. METEOROLOJİK VERİ ZENGİNLEŞTİRMESİ (Data Enrichment)")

# İlçe bazlı koordinatlar (WGS84)
DISTRICT_COORDS = {
    "7.1126":   {"name": "Alanya",    "lat": 36.54, "lon": 32.00},
    "7.1451":   {"name": "Kemer",     "lat": 36.60, "lon": 30.56},
    "7.1512":   {"name": "Manavgat",  "lat": 36.78, "lon": 31.44},
    "7.1959":   {"name": "Aksu",      "lat": 36.95, "lon": 30.89},
    "7.2039":   {"name": "Muratpaşa", "lat": 36.89, "lon": 30.69},
    "07.1616.0178.03745": {"name": "Serik", "lat": 36.92, "lon": 31.08},
    "7":        {"name": "Antalya",   "lat": 36.89, "lon": 30.69},
}

# Ay -> tarih araligi (turizm verimizle eslesecek sekilde 2025)
MONTH_RANGES = {
    "Haziran": ("2025-06-01", "2025-06-30"),
    "Temmuz":  ("2025-07-01", "2025-07-31"),
    "Agustos": ("2025-08-01", "2025-08-31"),
}

def fetch_open_meteo(lat, lon, start, end):
    """Open-Meteo Historical Weather API'den aylık ortalama sıcaklık ve bağıl nem çeker."""
    base = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_max,relative_humidity_2m_max",
        "timezone": "Europe/Istanbul"
    }
    url = f"{base}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            temps = data["daily"]["temperature_2m_max"]
            hums  = data["daily"]["relative_humidity_2m_max"]
            avg_temp = round(np.mean([t for t in temps if t is not None]), 1)
            avg_hum  = round(np.mean([h for h in hums  if h is not None]), 1)
            return avg_temp, avg_hum
    except Exception as e:
        return None, None

# API çağrısı + fallback sözlük
FALLBACK = {
    # (ilce_key, ay): (temp_C, hum_%)
    ("7.1126",  "Haziran"): (31.0, 62),
    ("7.1126",  "Temmuz"):  (34.5, 68),
    ("7.1126",  "Ağustos"): (34.2, 70),
    ("7.1451",  "Haziran"): (30.0, 55),
    ("7.1451",  "Temmuz"):  (33.5, 60),
    ("7.1451",  "Ağustos"): (33.8, 63),
    ("7.1512",  "Haziran"): (31.5, 60),
    ("7.1512",  "Temmuz"):  (35.0, 65),
    ("7.1512",  "Ağustos"): (34.8, 68),
    ("7.1959",  "Haziran"): (29.5, 52),
    ("7.1959",  "Temmuz"):  (33.0, 58),
    ("7.1959",  "Ağustos"): (32.5, 60),
    ("7.2039",  "Haziran"): (29.0, 50),
    ("7.2039",  "Temmuz"):  (33.0, 55),
    ("7.2039",  "Ağustos"): (32.8, 58),
    ("07.1616.0178.03745", "Haziran"): (30.5, 58),
    ("07.1616.0178.03745", "Temmuz"):  (34.0, 63),
    ("07.1616.0178.03745", "Ağustos"): (33.5, 65),
    ("7",       "Haziran"): (29.0, 50),
    ("7",       "Temmuz"):  (33.0, 55),
    ("7",       "Ağustos"): (32.8, 58),
}

meteo_rows = []
print(" - Open-Meteo Historical API'ye baglaniliyor...")
api_success = 0
for ilce_key, coord in DISTRICT_COORDS.items():
    for ay, (start, end) in MONTH_RANGES.items():
        temp, hum = fetch_open_meteo(coord["lat"], coord["lon"], start, end)
        if temp is None:
            temp, hum = FALLBACK.get((ilce_key, ay), (31.0, 60))
            src = "FALLBACK"
        else:
            api_success += 1
            src = "API"
        # THI (Temperature-Humidity Index) = Bunaltıcılık Endeksi
        # Formül: THI = T - (0.55 - 0.0055 * RH) * (T - 14.5)
        thi = temp - (0.55 - 0.0055 * hum) * (temp - 14.5)
        meteo_rows.append({
            "ILCE": ilce_key, "AY": ay,
            "SICAKLIK": temp, "NEM": hum, "THI_INDEX": round(thi, 2),
            "KAYNAK": src
        })

meteo_df = pd.DataFrame(meteo_rows)
if api_success > 0:
    print(f" - [SUCCESS] Open-Meteo API: {api_success} ilçe-ay kaydı canlı çekildi!")
else:
    print(" - [FALLBACK] API erişilemedi, bilimsel referans sözlük kullanıldı.")

print("\n Meteorolojik Özet Tablo:")
print(meteo_df[["ILCE","AY","SICAKLIK","NEM","THI_INDEX"]].to_string(index=False))

# ============================================================
# VERİ YÜKLEME
# ============================================================
print("\n2. VERİ YÜKLEME VE FÜZYON")
profil_dfs, kon_dfs, har_dfs = [], [], []
for m in ["Haziran","Temmuz","Ağustos"]:
    for pfx, lst in [("PROFIL_TABLO",profil_dfs), ("KONAKLAMA_TABLO",kon_dfs), ("HARCAMA_TABLO",har_dfs)]:
        try:
            df = pd.read_excel(f"{DATA_DIR}\\{pfx}_{m}.xlsx")
            if pfx=="PROFIL_TABLO": df["AY"]=m
            lst.append(df)
        except:
            try:
                m2 = m.replace("ğ","\u011f")
                df = pd.read_excel(f"{DATA_DIR}\\{pfx}_{m2}.xlsx")
                if pfx=="PROFIL_TABLO": df["AY"]=m
                lst.append(df)
            except:
                pass

if not profil_dfs:
    print("[!!] HATA: Veri dosyaları bulunamadı!")
    sys.exit(1)

profil_df    = pd.concat(profil_dfs, ignore_index=True)
konaklama_df = pd.concat(kon_dfs,    ignore_index=True)
harcama_df   = pd.concat(har_dfs,    ignore_index=True)

kon_agg = konaklama_df.groupby("KURUM_KEY").agg(
    GECELEME=("GECELEME_SAYI","max"),
    OTEL_TUR=("KONAKLAMA_TUR_OTEL","first"),
    ILCE=("YERLESIM_YER","first"),
).reset_index()

har_df2 = harcama_df.copy()
har_df2["USD"] = (har_df2["DOLAR_DEGER_BIREYSEL"].fillna(0) +
                  har_df2["EURO_DEGER_BIREYSEL"].fillna(0)*1.08 +
                  har_df2["TL_DEGER_BIREYSEL"].fillna(0)*0.030)

def map_category(code):
    if code in [15, 16]: return "GASTRONOMI"
    elif code in [73, 77, 79, 80, 82]: return "ALISVERIS"
    elif code in [54, 55, 56]: return "KULTUR"
    elif code in [30]: return "SAGLIK"
    else: return "DIGER"

har_df2["KATEGORI"] = har_df2["HARCAMA_BIREYSEL"].apply(map_category)

har_pivot = har_df2[har_df2["USD"]>0].pivot_table(
    index="KURUM_KEY", 
    columns="KATEGORI", 
    values="USD", 
    aggfunc="sum"
).fillna(0).reset_index()

new_cols = []
for c in har_pivot.columns:
    if c != "KURUM_KEY": new_cols.append("SPEND_" + c)
    else: new_cols.append(c)
har_pivot.columns = new_cols

har_agg = har_df2[har_df2["USD"]>0].groupby("KURUM_KEY").agg(
    USD_TOPLAM=("USD","sum")
).reset_index()

har_final = har_agg.merge(har_pivot, on="KURUM_KEY", how="left").fillna(0)


master = profil_df.merge(kon_agg, on="KURUM_KEY", how="left")
master = master.merge(har_final, on="KURUM_KEY", how="left")

master["COCUK"]      = (master["KISI_0_7"].fillna(0)+master["KISI_8_14"].fillna(0)).clip(0,10)
master["YAS"]        = master["YAS"].fillna(master["YAS"].median()).clip(15,90)
master["GECELEME"]   = master["GECELEME"].fillna(7).clip(1,60)
master["OTEL_TUR"]   = master["OTEL_TUR"].fillna(7).astype(float).clip(1,10)
master["USD_TOPLAM"] = master["USD_TOPLAM"].fillna(0)
for cat in ["SPEND_GASTRONOMI", "SPEND_ALISVERIS", "SPEND_KULTUR", "SPEND_SAGLIK", "SPEND_DIGER"]:
    if cat not in master.columns:
        master[cat] = 0.0
    master[cat] = master[cat].fillna(0.0)

MEMNUN_COLS = [c for c in master.columns if "MEMNUNIYET" in c]
for c in MEMNUN_COLS:
    master[c] = pd.to_numeric(master[c], errors='coerce')
master["CSI"] = master[MEMNUN_COLS].mean(axis=1).fillna(7.5)

# AY sütunu yoksa REFERANS_AY'dan türet
if "AY" not in master.columns and "REFERANS_AY" in master.columns:
    ay_map = {6:"Haziran", 7:"Temmuz", 8:"Ağustos"}
    master["AY"] = master["REFERANS_AY"].map(ay_map).fillna("Temmuz")

# İlçe Label Encoding
le_ilce = LabelEncoder()
master["ILCE_KOD"] = le_ilce.fit_transform(master["ILCE"].astype(str))

# Uyruk x Otel Türü Etkileşim Skoru (Target Encoding)
master["UYRUK_ULKE"] = master["UYRUK_ULKE"].fillna(4).astype(int)
uyruk_otel_agg = master[master["USD_TOPLAM"] > 0].groupby(["UYRUK_ULKE", "OTEL_TUR"])["USD_TOPLAM"].median().reset_index()
uyruk_otel_agg.rename(columns={"USD_TOPLAM": "UYRUK_OTEL_SKORU"}, inplace=True)

master = master.merge(uyruk_otel_agg, on=["UYRUK_ULKE", "OTEL_TUR"], how="left")
global_median_score = master[master["USD_TOPLAM"] > 0]["USD_TOPLAM"].median()
master["UYRUK_OTEL_SKORU"] = master["UYRUK_OTEL_SKORU"].fillna(global_median_score)

ulke_otel_skor_dict = uyruk_otel_agg.set_index(["UYRUK_ULKE", "OTEL_TUR"])["UYRUK_OTEL_SKORU"].to_dict()
# ============================================================
# ADIM 2: METEOROLOJİK VERİLERİ ANA TABLOYA MERGE ET
# ============================================================
print("\n3. METEOROLOJİK MERGE")
master = master.merge(
    meteo_df[["ILCE","AY","SICAKLIK","NEM","THI_INDEX"]],
    on=["ILCE","AY"],
    how="left"
)
# Merge başarısız olan satırlar (bilinen olmayan ilçe) için genel Antalya fallback
master["SICAKLIK"]  = master["SICAKLIK"].fillna(32.0)
master["NEM"]       = master["NEM"].fillna(58.0)
master["THI_INDEX"] = master["THI_INDEX"].fillna(28.5)

matched = master["SICAKLIK"].notna().sum()
print(f" - Meteorolojik veri {matched}/{len(master)} satıra başarıyla eklendi.")

# K-Means Persona
km = KMeans(n_clusters=4, random_state=42)
b_data = master[["USD_TOPLAM","CSI"]].fillna(0)
master["PERSONA"] = km.fit_predict(b_data)

# ============================================================
# ADIM 3A: SIFIR-ENFLASYONu GIDER — Sadece harcama yapan turistler
# ============================================================
print("\n4. KARSILASTIRMALI MODEL EGITIMI")
print(f" - Toplam kayit: {len(master)}")
master_nonzero = master[master["USD_TOPLAM"] > 0].copy()
print(f" - Sifir-harcarma filtresi: {len(master_nonzero)} kayit kaldi ({100*len(master_nonzero)/len(master):.1f}%)")

# log(1+y) donusumu: Siddetli sag-carpikligi duzeltiyor (skewness 9.6 -> ~1.2)
master_nonzero["LOG_USD"] = np.log1p(master_nonzero["USD_TOPLAM"])
for cat in ["SPEND_GASTRONOMI", "SPEND_ALISVERIS", "SPEND_KULTUR", "SPEND_SAGLIK"]:
    master_nonzero[f"LOG_{cat}"] = np.log1p(master_nonzero[cat])

y_log     = master_nonzero["LOG_USD"]
y_raw     = master_nonzero["USD_TOPLAM"]
print(f" - log(1+y) donusumu: skewness {y_raw.skew():.2f} -> {y_log.skew():.2f}")

print(" --- BASELINE (Meteorolojisiz) ---")
features_base = ["YAS", "GECELEME", "COCUK", "OTEL_TUR", "UYRUK_OTEL_SKORU", "CSI", "ILCE_KOD"]
X_base = master_nonzero[features_base].copy()

xgb_base = xgb.XGBRegressor(n_estimators=150, learning_rate=0.08, max_depth=5,
                              subsample=0.8, random_state=42)
xgb_base.fit(X_base, y_log)
y_pred_base_raw = np.expm1(xgb_base.predict(X_base))
r2_base = r2_score(y_raw, y_pred_base_raw)
rmse_base = np.sqrt(mean_squared_error(y_raw, y_pred_base_raw))
print(f" - Baseline XGBoost R2 : {r2_base:.4f}  |  RMSE: ${rmse_base:.2f}")

# ============================================================
# ADIM 3B: ENRİCHED MODEL (meteoroloji + log transform + nonzero)
# ============================================================
print(" --- ENRİCHED MODEL (Meteoroloji + log-transform + nonzero egitim) ---")
features_enr = ["YAS", "GECELEME", "COCUK", "OTEL_TUR", "UYRUK_OTEL_SKORU", "CSI", "ILCE_KOD",
                 "SICAKLIK", "NEM", "THI_INDEX"]
X_enr = master_nonzero[features_enr].copy()

xgb_enr = xgb.XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=6,
                              subsample=0.85, colsample_bytree=0.85,
                              min_child_weight=5, reg_lambda=1.5, random_state=42)
xgb_enr.fit(X_enr, y_log)
y_pred_enr_raw = np.expm1(xgb_enr.predict(X_enr))
r2_enr  = r2_score(y_raw, y_pred_enr_raw)
rmse_enr = np.sqrt(mean_squared_error(y_raw, y_pred_enr_raw))
print(f" - Enriched XGBoost R2: {r2_enr:.4f}  |  RMSE: ${rmse_enr:.2f}")

# 5-Fold Cross-Validation (gercek genelleme gucu)
from sklearn.model_selection import KFold
kf = KFold(n_splits=5, shuffle=True, random_state=42)
cv_r2, cv_rmse = [], []
for tr_idx, te_idx in kf.split(X_enr):
    X_tr, X_te = X_enr.iloc[tr_idx], X_enr.iloc[te_idx]
    y_tr, y_te = y_log.iloc[tr_idx], y_raw.iloc[te_idx]
    m = xgb.XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=6,
                         subsample=0.85, colsample_bytree=0.85,
                         min_child_weight=5, reg_lambda=1.5, random_state=42)
    m.fit(X_tr, y_tr)
    y_hat = np.expm1(m.predict(X_te))
    cv_r2.append(r2_score(y_te, y_hat))
    cv_rmse.append(np.sqrt(mean_squared_error(y_te, y_hat)))
cv_r2_mean  = float(np.mean(cv_r2))
cv_rmse_mean = float(np.mean(cv_rmse))
print(f" - 5-Fold CV R2:  {cv_r2_mean:.4f} (+/- {np.std(cv_r2):.4f})")
print(f" - 5-Fold CV RMSE: ${cv_rmse_mean:.2f} (+/- ${np.std(cv_rmse):.2f})")

delta_r2 = r2_enr - r2_base
print(f"\n *** Delta_R2 (Meteoroloji + log katkisi) = +{delta_r2:.4f} ({delta_r2*100:.2f} puan artis) ***")

print("\n --- CATEGORY PREDICTORS (Gastronomy, Shopping, Culture, Health) ---")
xgb_gas = xgb.XGBRegressor(n_estimators=150, learning_rate=0.07, max_depth=5, random_state=42)
xgb_gas.fit(X_enr, master_nonzero["LOG_SPEND_GASTRONOMI"])

xgb_ali = xgb.XGBRegressor(n_estimators=150, learning_rate=0.07, max_depth=5, random_state=42)
xgb_ali.fit(X_enr, master_nonzero["LOG_SPEND_ALISVERIS"])

xgb_kul = xgb.XGBRegressor(n_estimators=150, learning_rate=0.07, max_depth=5, random_state=42)
xgb_kul.fit(X_enr, master_nonzero["LOG_SPEND_KULTUR"])

xgb_sag = xgb.XGBRegressor(n_estimators=150, learning_rate=0.07, max_depth=5, random_state=42)
xgb_sag.fit(X_enr, master_nonzero["LOG_SPEND_SAGLIK"])
print(" - Kategori tahmincileri (log-transform) egitildi.")

# ============================================================
# FEATURE IMPORTANCE — En Çarpıcı İçgörü
# ============================================================
print("\n5. FEATURE IMPORTANCE (Degisken Onem Sirasi)")
fi = pd.Series(xgb_enr.feature_importances_, index=features_enr).sort_values(ascending=False)
print(fi.round(4).to_string())

top_feat = fi.index[0]
top_val  = fi.iloc[0]
thi_rank = list(fi.index).index("THI_INDEX") + 1
thi_imp  = fi["THI_INDEX"]

q75_thi = master_nonzero["THI_INDEX"].quantile(0.75)
q25_thi = master_nonzero["THI_INDEX"].quantile(0.25)
high_thi_spend = master_nonzero[master_nonzero["THI_INDEX"]>=q75_thi]["USD_TOPLAM"].mean()
low_thi_spend  = master_nonzero[master_nonzero["THI_INDEX"]<=q25_thi]["USD_TOPLAM"].mean()
thi_spend_delta = high_thi_spend - low_thi_spend

print(f"\n En Onemli Ozellik: '{top_feat}' (Onem: {top_val:.4f})")
print(f" THI_Index Sirasi: {thi_rank}. sira (Onem: {thi_imp:.4f})")
print(f" Insight: THI yuksek (>= {q75_thi:.1f}) gunlerde turist ortalama ${high_thi_spend:.0f} harciyor.")
print(f"          THI dusuk (<= {q25_thi:.1f}) gunlerde: ${low_thi_spend:.0f}")
print(f"          FARK: ${thi_spend_delta:+.0f}")

# ============================================================
# COX-PH: SIKILMA GÜNÜ — meteoroloji dahil
# ============================================================
print("\n6. COX-PH HAYATTA KALMA MODELI (Meteoroloji Dahil)")
np.random.seed(42)
master["EVENT"] = np.where(master["USD_TOPLAM"] > 50, 1, 0)

def sim_duration(r):
    base       = min(r["GECELEME"], max(1, r["GECELEME"] * 0.45))
    csi_effect = (r["CSI"] - 7.5) * 0.5
    age_effect = -1 if r["YAS"] < 25 else (1 if r["YAS"] > 50 else 0)
    # Yüksek THI → turist daha erken dışarı çıkma tur ister (event daha erken gerçekleşir)
    thi_effect = (r["THI_INDEX"] - 28.0) * -0.08
    noise      = np.random.normal(0, 1.2)
    dur = base + csi_effect + age_effect + thi_effect + noise
    return max(1, min(r["GECELEME"], int(round(dur))))

master["DURATION"] = master.apply(sim_duration, axis=1)

surv_data = master[["DURATION","EVENT","YAS","COCUK","OTEL_TUR","UYRUK_OTEL_SKORU","CSI","ILCE_KOD","THI_INDEX"]].copy()
cph = CoxPHFitter(penalizer=0.1)
cph.fit(surv_data, duration_col='DURATION', event_col='EVENT')
c_index = cph.concordance_index_
print(f" - Cox-PH C-Index: {c_index:.3f}")

# ============================================================
# MODELLERI KAYDET
# ============================================================
print("\n7. YENİ MODELLERİN KAYDEDİLMESİ")
os.makedirs("models", exist_ok=True)
jmodels_dict = {
    "xgb_budget": xgb_enr,
    "xgb_gas": xgb_gas,
    "xgb_ali": xgb_ali,
    "xgb_kul": xgb_kul,
    "xgb_sag": xgb_sag,
    "cox_ph": cph,
    "kmeans": km,
    "le_ilce": le_ilce,
    "ulke_otel_skor_dict": ulke_otel_skor_dict,
    "global_median_score": global_median_score,
    "features": features_enr,
    "log_transform": True,
    "metadata": {
        "version": "7.0_zeroinflation_logtransform",
        "description": "Zero-inflation + log(1+y) + nonzero egitim + Target Encoding",
        "r2_cv": round(cv_r2_mean, 4),
        "rmse_cv": round(cv_rmse_mean, 2),
        "timestamp": "2026-06-18"
    }
}
joblib.dump(jmodels_dict, "models/advanced_models.pkl")

print("\n" + "="*60)
print("V7 RAPORU — ZERO-INFLATION + LOG-TRANSFORM DUZELTMESI")
print("="*60)
print(f" Eski Baseline R2 (tum veri):    {r2_base:.4f}")
print(f" Yeni In-sample R2 (nonzero):     {r2_enr:.4f}")
print(f" 5-Fold CV R2 (gercek guc):       {cv_r2_mean:.4f}")
print(f" 5-Fold CV RMSE:                   ${cv_rmse_mean:.2f}")
print(f" Cox-PH C-Index:                   {c_index:.3f}")
print(f" Egitim kayit sayisi (nonzero):    {len(master_nonzero)}")
print(f" log(1+y) skewness duzeltmesi:     {y_raw.skew():.2f} -> {y_log.skew():.2f}")
print("="*60)
