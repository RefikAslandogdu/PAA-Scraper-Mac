from playwright.sync_api import sync_playwright
import time
import random
import os
import sys
import re


def get_paa_questions(query, num_questions=10):
    all_questions = []
    seen = set()

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

            # --- Soruları topla ---
            def collect():
                selectors = [
                    ("[data-q]", "attr"),
                    ("[jsname='Cpkphb'] [role='heading']", "text"),
                    ("[jsname='N760b'] [role='heading']", "text"),
                    ("[jsname='yEVEwb']", "text"),
                    (".related-question-pair [role='heading']", "text"),
                    (".wQiwMc [role='heading']", "text"),
                    ("div[jscontroller] [role='heading'][aria-level]", "text"),
                ]
                noise = {
                    "diğer sorular", "bu videoda", "hangi konuda",
                    "görüş bildirin", "geri bildirim",
                }

                def is_valid_question(text):
                    if not text or len(text) < 8 or len(text) > 150:
                        return False
                    low = text.lower()
                    if any(n in low for n in noise):
                        return False
                    return True

                for sel, mode in selectors:
                    try:
                        els = page.query_selector_all(sel)
                        for el in els:
                            q = (
                                el.get_attribute("data-q")
                                if mode == "attr"
                                else el.text_content().strip()
                            )
                            if q and is_valid_question(q) and q not in seen:
                                seen.add(q)
                                all_questions.append(q)
                    except Exception:
                        continue

            collect()

            # --- Tıklayarak genişlet (daha fazla soru yükle) ---
            if len(all_questions) < num_questions:
                for _ in range(6):
                    try:
                        expandables = page.query_selector_all(
                            "[data-q][aria-expanded='false']"
                        )
                        if not expandables:
                            expandables = page.query_selector_all(
                                ".related-question-pair"
                            )
                        if not expandables:
                            break

                        clicked = False
                        for el in expandables:
                            try:
                                el.scroll_into_view_if_needed()
                                time.sleep(0.3)
                                el.click()
                                time.sleep(random.uniform(1.2, 2.0))
                                clicked = True
                                break
                            except Exception:
                                continue

                        if not clicked:
                            break

                        collect()

                        if len(all_questions) >= num_questions:
                            break
                    except Exception:
                        break

            # --- Son çare: HTML'den regex ile çek ---
            if not all_questions:
                html = page.content()
                pattern = re.compile(r">([^<]{10,120}\?)<", re.UNICODE)
                matches = pattern.findall(html)
                for m in matches:
                    m = m.strip()
                    if m not in seen and 10 < len(m) < 150:
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
