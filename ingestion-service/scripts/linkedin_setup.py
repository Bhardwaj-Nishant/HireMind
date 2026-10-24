"""
One-time LinkedIn session setup for the linkedin_scraper library.

Run this once (and again whenever your session eventually expires):
    python scripts/linkedin_setup.py

It opens a real (visible) browser window, you log into LinkedIn by hand
(this script never sees or stores your password), and once logged in it
saves the session to linkedin_session.json — every later scraping run
reuses that file headlessly, no repeated manual login needed until it
expires.

Requires (one-time):
    pip install linkedin-scraper playwright
    playwright install chromium
"""
import asyncio
import os

from linkedin_scraper import BrowserManager, is_logged_in, wait_for_manual_login

SESSION_PATH = os.environ.get(
    "LINKEDIN_SESSION_PATH", os.path.join(os.path.dirname(__file__), "..", "linkedin_session.json")
)


async def main():
    print("Opening a browser window — log into LinkedIn manually, then this will continue automatically.")
    async with BrowserManager(headless=False) as browser:
        await browser.page.goto("https://www.linkedin.com/login")
        await wait_for_manual_login(browser.page)

        if not await is_logged_in(browser.page):
            print("Login wasn't detected — try running this again.")
            return

        # Best-effort: linkedin_scraper's public API clearly documents
        # BrowserManager.load_session(path) for reuse, but its save-side
        # method name isn't confirmed from where I could verify — if this
        # attribute doesn't exist under this exact name, the error here
        # will show what's actually available so we can fix it together.
        await browser.save_session(SESSION_PATH)

        # The file holds live login cookies (including li_at), so treat it
        # like a password: owner-only permissions, and never commit it.
        # It is listed in .gitignore; this is a second line of defence.
        try:
            os.chmod(SESSION_PATH, 0o600)
        except OSError:
            pass  # e.g. Windows, where POSIX modes don't apply

        print(f"Session saved to {SESSION_PATH}. You can now run LinkedIn scraping headlessly.")
        print("This file contains your LinkedIn login cookies. Do NOT commit or share it.")


if __name__ == "__main__":
    asyncio.run(main())