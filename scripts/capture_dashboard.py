"""Optional: capture the real running local app; requires Playwright + Chromium.

Start Streamlit first on port 8501. Install optional tooling separately:
  pip install playwright
  python -m playwright install chromium
This script never fabricates a dashboard image.
"""
from pathlib import Path
import argparse
from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', help='Optional existing Chromium executable')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=args.chromium)
        page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
        page.goto('http://127.0.0.1:8501', wait_until='networkidle')
        page.get_by_text('Economic sensitivity · complete global cohort', exact=True).wait_for(timeout=30000)
        page.locator('.js-plotly-plot').first.wait_for(timeout=30000)
        page.screenshot(path=str(root / 'screenshots/local_dashboard.png'), full_page=True)
        browser.close()
        print('Saved real local dashboard screenshot')


if __name__ == '__main__':
    main()
