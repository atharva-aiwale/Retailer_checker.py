import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import time
import subprocess
import sys

# ── Auto-install dependencies ─────────────────────────────────────────────────
def install_deps():
    for pkg in ["selenium", "webdriver-manager"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

install_deps()

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

TARGET_URL = "https://identitycentral.pg.com/groups"


# ── Debug helpers ─────────────────────────────────────────────────────────────
def dump_debug(driver, log_fn):
    try:
        driver.save_screenshot("debug_screenshot.png")
        log_fn("📸 Screenshot → debug_screenshot.png")
    except Exception:
        pass
    try:
        with open("debug_page_source.txt", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log_fn("📄 Page source → debug_page_source.txt")
    except Exception:
        pass


# ── Core automation ───────────────────────────────────────────────────────────
def search_retailers(user_id, retailer_list, log_fn):

    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    log_fn("🚀 Launching Chrome …")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    try:
        # ── 1. Open URL ───────────────────────────────────────────────────────
        log_fn(f"🌐 Opening {TARGET_URL} …")
        driver.get(TARGET_URL)
        time.sleep(2)

        # ── 2. Wait for manual login (up to 120 s, exit early when on /groups) ─
        log_fn("⏳ Waiting up to 120 s for you to log in manually …")
        log_fn("   ▶▶ Please log in in the Chrome window now.")
        for tick in range(120):
            time.sleep(1)
            if "identitycentral.pg.com/groups" in driver.current_url:
                log_fn(f"   ✅ Groups page detected after {tick+1}s — continuing!")
                break
            if tick % 10 == 9:
                log_fn(f"   {tick+1}s elapsed … still waiting …")
        else:
            raise Exception("Timed out waiting for login. Please try again.")

        # ── 3. Wait for React to render inputs (poll up to 30 s) ──────────────
        log_fn("⏳ Waiting for page inputs to render …")
        all_inputs = []
        for sec in range(30):
            time.sleep(1)
            all_inputs = driver.find_elements(By.XPATH, "//input")
            if all_inputs:
                log_fn(f"   ✅ {len(all_inputs)} input(s) visible after {sec+1}s")
                break
            if sec % 5 == 4:
                log_fn(f"   Still waiting for inputs … ({sec+1}s)")
        else:
            dump_debug(driver, log_fn)
            raise Exception("No <input> elements appeared within 30 s. See debug files.")

        # ── 4. Log all inputs found ───────────────────────────────────────────
        log_fn("🔎 Inputs found on page:")
        for i, inp in enumerate(all_inputs):
            log_fn(
                f"   [{i}] id={inp.get_attribute('id')!r}  "
                f"name={inp.get_attribute('name')!r}  "
                f"placeholder={inp.get_attribute('placeholder')!r}  "
                f"type={inp.get_attribute('type')!r}"
            )

        # ── 5. Locate Members field ───────────────────────────────────────────
        log_fn("🔍 Locating Members field …")
        members_field = None

        # Pass 1: match by placeholder / id / name / aria-label keywords
        for inp in all_inputs:
            attrs = " ".join([
                inp.get_attribute("placeholder") or "",
                inp.get_attribute("id") or "",
                inp.get_attribute("name") or "",
                inp.get_attribute("aria-label") or "",
            ]).lower()
            if any(kw in attrs for kw in ["member", "smith", "miller"]):
                members_field = inp
                log_fn(f"   ✅ Matched via attribute keywords.")
                break

        # Pass 2: label text → next sibling input
        if members_field is None:
            try:
                members_field = driver.find_element(
                    By.XPATH,
                    "//label[contains(translate(normalize-space(.),'MEMBERS','members'),'members')]"
                    "/following::input[1]"
                )
                log_fn("   ✅ Matched via label 'Members'.")
            except Exception:
                pass

        # Pass 3: positional fallback — Members is the 2nd input per the screenshot
        if members_field is None and len(all_inputs) >= 2:
            members_field = all_inputs[1]
            log_fn("   ⚠️  Using positional fallback: input[1] (2nd input).")

        if members_field is None:
            dump_debug(driver, log_fn)
            raise Exception("Cannot find the Members input field.")

        members_field.click()
        time.sleep(0.3)
        members_field.clear()
        members_field.send_keys(user_id)
        log_fn(f"   ✏️  Entered user ID: {user_id}")
        time.sleep(1)

        # ── 6. Click Search button ────────────────────────────────────────────
        log_fn("🖱️  Locating Search button …")
        search_btn = None
        for btn in driver.find_elements(By.XPATH, "//button"):
            if btn.text.strip().lower() == "search":
                search_btn = btn
                break
        if search_btn is None:
            for btn in driver.find_elements(By.XPATH, "//button"):
                if "search" in btn.text.lower():
                    search_btn = btn
                    break
        if search_btn is None:
            dump_debug(driver, log_fn)
            raise Exception("Cannot find the Search button.")

        log_fn(f"   ✅ Search button: text={search_btn.text!r}")
        search_btn.click()
        log_fn("⏳ Waiting for results …")
        time.sleep(6)

        # ── 7. Scroll down and click "All" button ─────────────────────────────
        log_fn("🖱️  Scrolling down to find 'All' button …")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        all_btn = None
        # Try exact text match first
        for btn in driver.find_elements(By.XPATH, "//button | //a | //span"):
            if btn.text.strip().lower() == "all":
                all_btn = btn
                break
        # Fallback: contains 'all' as a standalone word
        if all_btn is None:
            for btn in driver.find_elements(By.XPATH, "//button | //a"):
                txt = btn.text.strip().lower()
                if txt in ("all", "show all", "view all", "select all"):
                    all_btn = btn
                    break

        if all_btn:
            log_fn(f"   ✅ 'All' button found: text={all_btn.text!r} — clicking …")
            driver.execute_script("arguments[0].scrollIntoView(true);", all_btn)
            time.sleep(1)
            all_btn.click()
            log_fn("⏳ Waiting for all results to load …")
            time.sleep(5)
        else:
            log_fn("   ⚠️  No 'All' button found — proceeding with visible results.")

        # ── 8. Scrape result rows ─────────────────────────────────────────────
        log_fn("📋 Scraping results …")
        # Scroll back up so all rendered rows are in DOM
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        raw_els = driver.find_elements(
            By.XPATH,
            "//table//td | //tbody//tr//td[1] | "
            "//ul//li | //ol//li | "
            "//div[contains(@class,'result')]//span | "
            "//div[contains(@class,'group')]//span | "
            "//a[contains(@href,'group')]"
        )
        found_ids = set()
        for el in raw_els:
            txt = el.text.strip()
            if txt and len(txt) < 120:
                found_ids.add(txt.upper())

        log_fn(f"   Entries scraped: {len(found_ids)}")
        if found_ids:
            log_fn(f"   Sample (first 10): {list(found_ids)[:10]}")

        # ── 9. Match retailers ────────────────────────────────────────────────
        retailer_map = {r.strip().upper(): r.strip() for r in retailer_list}
        present = [retailer_map[k] for k in retailer_map if k in found_ids]
        absent  = [retailer_map[k] for k in retailer_map if k not in found_ids]

        return present, absent, list(found_ids)

    except Exception:
        dump_debug(driver, log_fn)
        raise

    finally:
        log_fn("⏸️  Keeping browser open 10 s …")
        time.sleep(10)
        driver.quit()
        log_fn("🏁 Browser closed.")


# ── GUI ───────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Retailer Presence Checker – Identity Central")
        self.geometry("700x760")
        self.resizable(True, True)
        self.configure(bg="#1e1e2e")

        LABEL = dict(bg="#1e1e2e", fg="#cdd6f4", font=("Segoe UI", 10, "bold"))
        ENTRY = dict(bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                     relief="flat", font=("Consolas", 10), bd=5)
        BTN   = dict(relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2", padx=12, pady=6)

        tk.Label(self, text="User ID:", **LABEL).pack(anchor="w", padx=20, pady=(18, 2))
        self.user_entry = tk.Entry(self, width=60, **ENTRY)
        self.user_entry.pack(padx=20, pady=(0, 10), fill="x")

        tk.Label(self, text="Retailer List (one ID per line):", **LABEL).pack(anchor="w", padx=20, pady=(4, 2))
        self.retailer_box = tk.Text(self, width=60, height=8, **ENTRY)
        self.retailer_box.pack(padx=20, pady=(0, 10), fill="x")

        bf = tk.Frame(self, bg="#1e1e2e")
        bf.pack(pady=6)
        self.run_btn = tk.Button(bf, text="▶  Run Check", bg="#89b4fa", fg="#1e1e2e",
                                 command=self._start, **BTN)
        self.run_btn.grid(row=0, column=0, padx=8)
        tk.Button(bf, text="⟳  Clear", bg="#45475a", fg="#cdd6f4",
                  command=self._clear, **BTN).grid(row=0, column=1, padx=8)

        tk.Label(self, text="Log:", **LABEL).pack(anchor="w", padx=20, pady=(8, 2))
        self.log_area = scrolledtext.ScrolledText(
            self, width=80, height=14, state="disabled",
            bg="#181825", fg="#a6e3a1", font=("Consolas", 8), relief="flat", bd=5)
        self.log_area.pack(padx=20, pady=(0, 6), fill="both", expand=True)

        rf = tk.Frame(self, bg="#1e1e2e")
        rf.pack(padx=20, pady=6, fill="both", expand=True)

        tk.Label(rf, text="✅ Present:", **LABEL).grid(row=0, column=0, sticky="w")
        self.present_box = scrolledtext.ScrolledText(
            rf, width=28, height=8, state="disabled",
            bg="#1e3a2a", fg="#a6e3a1", font=("Consolas", 9), relief="flat", bd=4)
        self.present_box.grid(row=1, column=0, padx=(0, 10), sticky="nsew")

        tk.Label(rf, text="❌ Absent:", **LABEL).grid(row=0, column=1, sticky="w")
        self.absent_box = scrolledtext.ScrolledText(
            rf, width=28, height=8, state="disabled",
            bg="#3a1e1e", fg="#f38ba8", font=("Consolas", 9), relief="flat", bd=4)
        self.absent_box.grid(row=1, column=1, sticky="nsew")

        rf.columnconfigure(0, weight=1)
        rf.columnconfigure(1, weight=1)
        rf.rowconfigure(1, weight=1)

    def _log(self, msg):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", msg + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def _clear(self):
        for b in (self.log_area, self.present_box, self.absent_box):
            b.configure(state="normal")
            b.delete("1.0", "end")
            b.configure(state="disabled")

    def _fill(self, box, items):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", "\n".join(items) if items else "(none)")
        box.configure(state="disabled")

    def _start(self):
        uid   = self.user_entry.get().strip()
        rlist = [r.strip() for r in self.retailer_box.get("1.0", "end").splitlines() if r.strip()]
        if not uid:
            messagebox.showerror("Error", "Please enter a User ID."); return
        if not rlist:
            messagebox.showerror("Error", "Please enter at least one Retailer ID."); return

        self.run_btn.configure(state="disabled", text="Running …")
        self._clear()
        self._log(f"User ID   : {uid}")
        self._log(f"Retailers : {len(rlist)} provided")
        self._log("-" * 60)

        def worker():
            try:
                present, absent, _ = search_retailers(uid, rlist, self._log)
                self._log("-" * 60)
                self._log(f"✅ Present ({len(present)}): {', '.join(present) or 'None'}")
                self._log(f"❌ Absent  ({len(absent)}):  {', '.join(absent) or 'None'}")
                self.after(0, lambda: self._fill(self.present_box, present))
                self.after(0, lambda: self._fill(self.absent_box, absent))
                self.after(0, lambda: messagebox.showinfo(
                    "Done", f"Present: {len(present)}\nAbsent: {len(absent)}"))
            except Exception as e:
                self._log(f"💥 ERROR: {e}")
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, lambda: self.run_btn.configure(state="normal", text="▶  Run Check"))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
