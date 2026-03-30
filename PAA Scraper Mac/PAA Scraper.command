#!/bin/bash
# ============================================
#  Google PAA Scraper - Mac Launcher
#  Çift tıkla, gerisini halleder.
# ============================================

cd "$(dirname "$0")"

echo "=================================================="
echo "  Google PAA Scraper"
echo "=================================================="
echo ""

# --- Python kontrolü ---
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "HATA: Python bulunamadı!"
    echo "Lütfen https://www.python.org/downloads/ adresinden Python 3 yükleyin."
    echo ""
    read -p "Kapatmak için Enter'a basın..."
    exit 1
fi

echo "Python: $($PY --version)"

# --- İlk kurulum (venv + bağımlılıklar) ---
if [ ! -d ".venv" ]; then
    echo ""
    echo "İlk çalıştırma - ortam hazırlanıyor..."
    echo ""

    echo "[1/3] Sanal ortam oluşturuluyor..."
    $PY -m venv .venv

    echo "[2/3] Bağımlılıklar yükleniyor..."
    .venv/bin/pip install --upgrade pip -q
    .venv/bin/pip install -r requirements.txt -q

    echo "[3/3] Chromium tarayıcı indiriliyor..."
    .venv/bin/python -m playwright install chromium

    echo ""
    echo "Kurulum tamamlandı!"
fi

# --- Sanal ortamı aktifle ---
source .venv/bin/activate

# --- Tarayıcıyı aç ve sunucuyu başlat ---
echo ""
echo "Sunucu başlatılıyor: http://localhost:5000"
echo "Kapatmak için bu pencereyi kapatın veya Ctrl+C basın."
echo ""

# 1.5 saniye sonra tarayıcıyı aç (arka planda)
(sleep 1.5 && open "http://localhost:5000") &

# Flask sunucusunu başlat
$PY app.py
