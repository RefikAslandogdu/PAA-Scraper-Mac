from playwright.sync_api import sync_playwright
import time
import random
import os
import sys
import re


# PAA container'ını bulmak için kullanılan selector'lar
_PAA_CONTAINER_SELECTORS = [
    "div[data-sgrd]",                          # ana PAA wrapper
    "div[jscontroller][jsname] div[data-q]",   # data-q içeren wrapper
    ".related-question-pair",                   # eski yapı
]

# Gürültü filtreleme
_NOISE = {
    "diğer sorular", "bu videoda", "hangi konuda", "görüş bildirin",
    "geri bildirim", "ilgili aramalar", "sık sorulan sorular",
    "bu neden oldu", "daha fazla bilgi",
}


def _is_valid_question(text):
    """Gerçek bir PAA sorusu mu kontrol et."""
    if not text or len(text) < 10 or len(text) > 150:
        return False
    low = text.lower().strip()
    if any(n in low for n in _NOISE):
        return False
    # Çok fazla satır içeren cevap metinlerini filtrele
    if text.count("\n") > 1:
        return False
    # Soru işareti ile bitmeli VEYA soru kalıpları içermeli
    question_patterns = ["?", "nedir", "nasıl", "neden", "ne kadar", "hangi",
                         "kaç", "kim", "nereye", "neresi", "nereleri", "ne zaman",
                         "mı", "mi", "mu", "mü", "what", "how", "why", "when"]
    if not any(p in low for p in question_patterns):
        return False
    # Cevap gibi görünen metinleri filtrele
    answer_signs = ["şu şekildedir", "işte ", "şunlardır", "aşağıdaki"]
    if any(s in low for s in answer_signs):
        return False
    return True


def _collect_from_data_q(page):
    """En güvenilir yöntem: data-q attribute'undan soruları çek."""
    questions = []
    try:
        els = page.query_selector_all("[data-q]")
        for el in els:
            q = el.get_attribute("data-q")
            if q and _is_valid_question(q):
                questions.append(q.strip())
    except Exception:
        pass
    return questions


def _collect_from_headings(page):
    """PAA bölümündeki heading elementlerinden soruları çek."""
    questions = []
    # Sadece PAA container'ı içindeki heading'lere bak
    selectors = [
        "[jsname='Cpkphb'] [role='heading']",
        "[jsname='N760b'] [role='heading']",
        ".related-question-pair [role='heading']",
        ".wQiwMc [role='heading']",
    ]
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            for el in els:
                q = el.text_content()
                if q:
                    # Sadece ilk satırı al (cevap metni karışmasın)
                    q = q.strip().split("\n")[0].strip()
                    if _is_valid_question(q):
                        questions.append(q)
        except Exception:
            continue
    return questions


def _click_to_expand(page, already_clicked):
    """Bir PAA sorusuna tıklayarak yeni soruların yüklenmesini sağla."""
    expandables = page.query_selector_all("[data-q][aria-expanded='false']")

    for el in expandables:
        try:
            q = el.get_attribute("data-q") or ""
            if q in already_clicked:
                continue
            already_clicked.add(q)
            el.scroll_into_view_if_needed()
            time.sleep(0.3)
            el.click()
            time.sleep(random.uniform(1.0, 1.8))
            return True
        except Exception:
            continue
    return False


def get_paa_questions(query, num_questions=10):
    all_questions = []
    seen = set()

    def add_questions(new_qs):
        for q in new_qs:
            if q not in seen:
                seen.add(q)
                all_questions.append(q)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-web-security",
            ],
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
        )

        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        try:
            url = f"https://www.google.com/search?q={query}&hl=tr&gl=tr&num=10"
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(random.uniform(2.5, 4.0))

            # Cookie popup kapat
            for text in ["Kabul et", "Tümünü kabul et", "Accept all", "Agree"]:
                try:
                    btn = page.locator(f"button:has-text('{text}')").first
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        time.sleep(1)
                        break
                except Exception:
                    pass

            # Scroll ile PAA'yı tetikle
            page.evaluate("window.scrollBy(0, 600)")
            time.sleep(1.5)
            page.evaluate("window.scrollBy(0, 400)")
            time.sleep(1.0)

            # --- 1. Adım: data-q ile topla (en güvenilir) ---
            add_questions(_collect_from_data_q(page))

            # --- 2. Adım: heading'lerden topla (fallback) ---
            if len(all_questions) < num_questions:
                add_questions(_collect_from_headings(page))

            # --- 3. Adım: Tıklayarak genişlet ---
            if len(all_questions) < num_questions:
                already_clicked = set()
                for _ in range(8):
                    if not _click_to_expand(page, already_clicked):
                        break
                    # Sadece data-q'dan topla (heading'ler cevap karıştırır)
                    add_questions(_collect_from_data_q(page))
                    if len(all_questions) >= num_questions:
                        break

            # --- 4. Adım: Son çare - regex ile HTML'den çek ---
            if not all_questions:
                html = page.content()
                pattern = re.compile(r">([^<]{10,120}\?)<", re.UNICODE)
                matches = pattern.findall(html)
                for m in matches:
                    m = m.strip()
                    if _is_valid_question(m) and m not in seen:
                        seen.add(m)
                        all_questions.append(m)
                    if len(all_questions) >= num_questions:
                        break

            # Debug: HTML kaydet
            if getattr(sys, "frozen", False):
                _dir = os.path.dirname(sys.executable)
            else:
                _dir = os.path.dirname(os.path.abspath(__file__))
            try:
                debug_path = os.path.join(_dir, "debug_page.html")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(page.content())
            except OSError:
                pass

        finally:
            browser.close()

    return all_questions[:num_questions]
