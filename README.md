# VisitAntalya SuperApp ML Engine 🚀

VisitAntalya SuperApp ML Engine, Antalya bölgesine gelen turistlerin **tatil memnuniyetlerini, bütçe segmentlerini ve tur satın alma olasılıklarını** makine öğrenmesi (Gradient Boosting & Bayesian Inference) kullanarak tahmin eden yenilikçi bir yapay zeka (XAI) destekli karar sistemidir.

## 🌟 Öne Çıkan Özellikler

- **Otonom Karar Motoru (GBM):** Turistin uyruğu, yaşı, konaklama süresi ve otel yıldızına göre milisaniyeler içinde "Tahmini Harcama Bütçesi" (USD) çıkarır.
- **Bayesçi Geri Bildirim Döngüsü:** Sistem her "Kabul" veya "Red" geri bildiriminde kendini günceller. Turistlerin fiyata olan duyarlılıklarını canlı olarak öğrenir.
- **Explainable AI (XAI) Paneli:** Modelin neden o kararı aldığını (Örn: Almanların X. gündeki sıkılma eğrisi) interaktif `Chart.js` grafikleriyle kanıtlar.
- **Mobil Öncelikli (PWA) Arayüz:** Modern Glassmorphism (cam tasarımı) mimarisiyle kodlanan arayüz, telefon ve tabletlerde kusursuz bir mobil uygulama deneyimi yaşatır.
- **Ultra Ölçeklenebilir:** Modeller binary formatta (`.pkl`) diske kaydedildiği için veritabanı boyutundan bağımsız anında yanıt (Zero-Latency) verir.

## 🛠️ Teknoloji Yığını (Tech Stack)

- **Backend:** Python 3, Flask (RESTful API)
- **Machine Learning:** Scikit-Learn (GradientBoostingRegressor), Joblib, Numpy, Pandas
- **Frontend:** HTML5, Vanilla JS, CSS3 (Mobile-First / PWA), Chart.js (XAI Grafikleri)

## 📦 Kurulum ve Çalıştırma

Bu projeyi yerel ortamınızda çalıştırmak için:

1. Depoyu klonlayın:
   ```bash
   git clone https://github.com/KULLANICI_ADINIZ/visitantalya-ml.git
   cd visitantalya-ml
   ```

2. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install flask scikit-learn pandas numpy joblib
   ```

3. Modellerin bulunduğu klasörde Flask sunucusunu başlatın:
   ```bash
   python app.py
   ```

4. Tarayıcınızdan uygulamaya gidin: `http://127.0.0.1:5000`

## 📊 İstatistiksel Kanıt (Explainable AI)

Tahmin motoru sadece sonuç üretmez, aynı zamanda:
- **Çöküş Eğrisi (Decay Curve):** Turistin tatilinin kaçıncı gününde sıkılacağını ve tur teklifinin hangi gün yapılması gerektiğini çizer.
- **Bütçe Kıyaslaması:** Ülke medyan harcaması ile GBM'in tahmin ettiği bütçeyi kıyaslar.

---
*Geliştirici:* Veri Bilimi ve Yapay Zeka Mimari odaklı tasarlanmıştır.
