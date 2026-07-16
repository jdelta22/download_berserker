import os
from pathlib import Path

# Playwright normally resolves browser binaries relative to its driver
# folder. Inside a PyInstaller --onefile executable, that folder is a fresh,
# random temp extraction directory (_MEI...) created on every launch — so
# anything installed there vanishes the moment that process exits, and a
# separate process (like our --install-browsers re-exec) gets its own,
# different _MEI folder entirely. Pinning PLAYWRIGHT_BROWSERS_PATH to a
# stable folder outside any temp extraction fixes this: install once, and
# every future launch (GUI or install subprocess) looks in the same place.
_BROWSERS_DIR = Path.home() / ".manga_downloader" / "browsers"
_BROWSERS_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_BROWSERS_DIR))

import asyncio
import logging
import queue
import subprocess
import sys
import threading
import webbrowser

import customtkinter as ctk
from PIL import Image

from scrapper import download_chapter, normalize_chapter
from convert_to_pdf import convert_chapter_to_pdf

ctk.set_appearance_mode("dark")

# ---------------------------------------------------------------------------
# Project info shown in the header. Adjust these to match your repo/site.
# ---------------------------------------------------------------------------

GITHUB_URL = "https://github.com/jdelta22/SEU_REPOSITORIO"  # TODO: point to the actual repo
ORIGINAL_SITE_URL = "https://readberserk.com"


def resource_path(relative_path: str) -> Path:
    """
    Resolve the absolute path to a bundled resource (e.g. an image under assets/).

    Works both when running app.py directly (dev) and when running inside a
    PyInstaller --onefile executable, where bundled data (via --add-data)
    lives in a temporary extraction folder exposed as sys._MEIPASS, not in
    the current working directory.
    """
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base_path / relative_path


LOGO_PATH = resource_path("assets/logo.png")  # drop the chosen image here (any size, it gets resized)


def is_chromium_installed() -> bool:
    """Check whether Playwright's Chromium build is already downloaded on this machine."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Thread-safe logging: background threads put log records into a queue,
# the GUI drains that queue on the main thread and writes into the textbox.
# ---------------------------------------------------------------------------

log_queue: "queue.Queue" = queue.Queue()


class QueueLogHandler(logging.Handler):
    def emit(self, record):
        log_queue.put(("log", self.format(record)))


def setup_logging():
    handler = QueueLogHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)


class HeaderFrame(ctk.CTkFrame):
    """Static header shown above the main frame: title, objective, source and links."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        if LOGO_PATH.exists():
            pil_image = Image.open(LOGO_PATH)
            logo_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(110, 110))
            self.logo_label = ctk.CTkLabel(self, image=logo_image, text="")
            self.logo_label.pack(pady=(10, 5))

        self.title_label = ctk.CTkLabel(
            self, text="Manga Downloader", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(pady=(5, 2))

        self.objective_label = ctk.CTkLabel(
            self,
            text="Downloads manga chapters as images and converts them into a single PDF per chapter.",
            wraplength=440,
            justify="center",
        )
        self.objective_label.pack(pady=2)

        self.source_label = ctk.CTkLabel(
            self,
            text=f"Chapters are scraped from {ORIGINAL_SITE_URL}",
            wraplength=440,
            justify="center",
            text_color="gray70",
        )
        self.source_label.pack(pady=(2, 8))

        links_frame = ctk.CTkFrame(self, fg_color="transparent")
        links_frame.pack(pady=(0, 5))

        self.github_link = ctk.CTkLabel(links_frame, text="GitHub", text_color="#4EA1FF", cursor="hand2")
        self.github_link.grid(row=0, column=0, padx=12)
        self.github_link.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_URL))

        self.site_link = ctk.CTkLabel(links_frame, text="Original Site", text_color="#4EA1FF", cursor="hand2")
        self.site_link.grid(row=0, column=1, padx=12)
        self.site_link.bind("<Button-1>", lambda e: webbrowser.open(ORIGINAL_SITE_URL))


class MyFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.label = ctk.CTkLabel(self, text="Enter the Chapter number:")
        self.label.pack(pady=10)

        self.chapter_number = ctk.CTkEntry(self, placeholder_text="Chapter number", textvariable=ctk.StringVar())
        self.chapter_number.pack(pady=10)

        self.label_warning = ctk.CTkLabel(
            self,
            text="Please enter a valid chapter number.\n"
                 "If you don't know what chapter is, take the number from the original site\n"
                 "Prequels are in format a0, b0, c0 ... p0\n"
                 "Extra chapters don't have a specific format",
            text_color="red",
        )
        self.label_warning.pack(pady=10)

        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.pack(pady=10)

        self.download_button = ctk.CTkButton(buttons_frame, text="Download", command=self.start_download)
        self.download_button.grid(row=0, column=0, padx=5)

        self.convert_button = ctk.CTkButton(buttons_frame, text="Convert to PDF", command=self.start_convert)
        self.convert_button.grid(row=0, column=1, padx=5)

        self.install_button = ctk.CTkButton(
            buttons_frame, text="Install Chromium", command=self.start_install_browsers,
            fg_color="#8B5A2B", hover_color="#6E4722",
        )
        self.install_button.grid(row=0, column=2, padx=5)

        self.chromium_status_label = ctk.CTkLabel(self, text="Checking Chromium installation...", text_color="gray70")
        self.chromium_status_label.pack(pady=(0, 5))

        self.progress_bar = ctk.CTkProgressBar(self, width=350)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

        self.progress_label = ctk.CTkLabel(self, text="")
        self.progress_label.pack()

        self.log_textbox = ctk.CTkTextbox(self, width=450, height=220, state="disabled")
        self.log_textbox.pack(pady=10)

        # Poll the queue for log/progress/done messages coming from background threads.
        self.after(100, self.poll_queue)

        # Check Chromium status without blocking the GUI on startup.
        threading.Thread(target=self.check_chromium_status, daemon=True).start()

    # -- actions -----------------------------------------------------------

    def check_chromium_status(self):
        installed = is_chromium_installed()
        log_queue.put(("chromium_status", installed))

    def start_install_browsers(self):
        self.set_buttons_enabled(False)
        self.append_log("Installing Chromium... this can take a few minutes on first run.")
        self.chromium_status_label.configure(text="Installing Chromium...")

        def worker():
            try:
                # Re-invoke this same executable with a marker flag instead of
                # depending on a system Python (which may not exist on the
                # client machine). See the "--install-browsers" handling below.
                process = subprocess.Popen(
                    [sys.executable, "--install-browsers"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        log_queue.put(("log", line))
                process.wait()
                log_queue.put(("install_done", process.returncode == 0))
            except Exception as e:
                log_queue.put(("error", f"Failed to install Chromium: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def start_download(self):
        chapter = self.chapter_number.get().strip()
        if not chapter:
            self.append_log("Please enter a chapter number before downloading.")
            return

        self.set_buttons_enabled(False)
        self.progress_bar.set(0)
        self.progress_label.configure(text="Starting download...")

        def on_progress(current, total):
            log_queue.put(("progress", current, total))

        def worker():
            try:
                result = asyncio.run(
                    download_chapter(chapter, progress_callback=on_progress)
                )
                log_queue.put(("download_done", result))
            except Exception as e:
                log_queue.put(("error", f"Unexpected error while downloading: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def start_convert(self):
        chapter = self.chapter_number.get().strip()
        if not chapter:
            self.append_log("Please enter a chapter number before converting.")
            return

        self.set_buttons_enabled(False)
        self.progress_label.configure(text="Converting to PDF...")

        chapter_dir = Path("capitulos") / f"capitulo_{normalize_chapter(chapter)}"

        def worker():
            try:
                result = convert_chapter_to_pdf(chapter_dir)
                log_queue.put(("convert_done", result))
            except Exception as e:
                log_queue.put(("error", f"Unexpected error while converting: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    # -- queue polling / GUI updates ---------------------------------------

    def poll_queue(self):
        try:
            while True:
                item = log_queue.get_nowait()
                kind = item[0]

                if kind == "log":
                    self.append_log(item[1])

                elif kind == "progress":
                    _, current, total = item
                    if total:
                        self.progress_bar.set(current / total)
                        self.progress_label.configure(text=f"{current}/{total} images")

                elif kind == "download_done":
                    result = item[1]
                    self.set_buttons_enabled(True)
                    if result["success"]:
                        self.append_log(
                            f"Download finished: {result['downloaded']}/{result['total']} images saved "
                            f"to {result['output_dir']}"
                        )
                        self.progress_label.configure(text="Download complete")
                    else:
                        self.append_log(f"Download failed: {result['error']}")
                        self.progress_label.configure(text="Download failed")

                elif kind == "convert_done":
                    result = item[1]
                    self.set_buttons_enabled(True)
                    if result["success"]:
                        self.append_log(f"PDF created: {result['pdf_path']}")
                        self.progress_label.configure(text="Conversion complete")
                    else:
                        self.append_log(f"Conversion failed: {result['error']}")
                        self.progress_label.configure(text="Conversion failed")

                elif kind == "chromium_status":
                    installed = item[1]
                    if installed:
                        self.chromium_status_label.configure(text="Chromium is installed.", text_color="gray70")
                    else:
                        self.chromium_status_label.configure(
                            text="Chromium not found — click 'Install Chromium' before downloading.",
                            text_color="orange",
                        )

                elif kind == "install_done":
                    success = item[1]
                    self.set_buttons_enabled(True)
                    if success:
                        self.append_log("Chromium installed successfully.")
                        self.chromium_status_label.configure(text="Chromium is installed.", text_color="gray70")
                    else:
                        self.append_log("Chromium installation failed. Check the log above for details.")
                        self.chromium_status_label.configure(
                            text="Chromium installation failed.", text_color="red"
                        )

                elif kind == "error":
                    self.set_buttons_enabled(True)
                    self.append_log(item[1])

        except queue.Empty:
            pass

        self.after(100, self.poll_queue)

    def append_log(self, message: str):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def set_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.download_button.configure(state=state)
        self.convert_button.configure(state=state)
        self.install_button.configure(state=state)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Manga Downloader")
        self.geometry("500x780")
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.header = HeaderFrame(master=self)
        self.header.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="ew")

        self.my_frame = MyFrame(master=self)
        self.my_frame.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")


def run_browser_install():
    """
    Entry point used when this executable is re-invoked with --install-browsers.
    Runs `playwright install chromium` and prints progress to stdout so the
    parent GUI process (which launched us as a subprocess) can stream it live.
    """
    from playwright.__main__ import main as playwright_main

    sys.argv = ["playwright", "install", "chromium"]
    playwright_main()


if __name__ == "__main__":
    if "--install-browsers" in sys.argv:
        run_browser_install()
        sys.exit(0)

    setup_logging()
    app = App()
    app.mainloop()