import time
from playwright.sync_api import sync_playwright

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        print("Goto mail.google.com with domcontentloaded...")
        page.goto("https://mail.google.com/", wait_until="domcontentloaded")
        print("URL after domcontentloaded:", page.url)
        time.sleep(2)
        print("URL after 2s:", page.url)
        browser.close()

if __name__ == "__main__":
    test()
