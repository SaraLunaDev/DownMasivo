import customtkinter as ctk
import tkinter as tk
import threading
import json
import os
import yt_dlp
from pathlib import Path
import glob
import datetime

CONFIG_FILE = "config.json"
DEFAULT_FONT = ("Segoe UI", 13)
ACCENT_COLOR = "#4a6fa5"
DARK_BG = "#23272e"

default_download_path = str(Path.home() / "Downloads")
default_config = {
    "download_dir": default_download_path,
    "convert_to_webm": False,
    "last_format": "MP4"
}

def get_ffmpeg_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_exe = os.path.join(base_dir, "ffmpeg", "ffmpeg.exe")
    return ffmpeg_exe

def get_ffprobe_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ffprobe_exe = os.path.join(base_dir, "ffmpeg", "ffprobe.exe")
    return ffprobe_exe

def check_ffmpeg():
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()
    if not (os.path.isfile(ffmpeg_path) and os.path.isfile(ffprobe_path)):
        ctk.CTkMessagebox(title="Falta ffmpeg", message="No se encontró ffmpeg.exe o ffprobe.exe. Descárgalos y colócalos en una carpeta llamada 'ffmpeg' junto al programa.", icon="cancel")
        return False
    return True

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return default_config.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

config = load_config()

class VideoDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.iconbitmap("icono.ico")  # <-- Add this line
        self.title(" DownMasivo")
        self.geometry("450x120")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        if not check_ffmpeg():
            self.destroy()
            return

        self.cancel_flag = False
        self.download_thread = None
        self._ydl_instance = None
        self._partial_filename = None

        # URL + Format + Folder row
        url_row = ctk.CTkFrame(self, fg_color="transparent")
        url_row.pack(fill="x", padx=24, pady=(18, 0))

        self.url_var = ctk.StringVar()
        ROW_HEIGHT = 26

        self.url_entry = ctk.CTkEntry(
            url_row, textvariable=self.url_var, width=270, height=ROW_HEIGHT, font=DEFAULT_FONT
        )
        self.url_entry.pack(side="left", padx=(0, 8), pady=0)

        self.format_var = ctk.StringVar(value=config.get("last_format", "MP4"))
        self.format_selector = ctk.CTkComboBox(
            url_row,
            variable=self.format_var,
            values=["MP4", "WEBM", "MP3", "OGG"],
            width=80,
            height=ROW_HEIGHT,
            font=DEFAULT_FONT,
            dropdown_font=DEFAULT_FONT,
            state="readonly"
        )
        self.format_selector.pack(side="left", padx=(0, 8), pady=0)
        self.format_selector.bind("<<ComboboxSelected>>", self.on_format_change)

        self.folder_var = ctk.StringVar(value=config.get("download_dir", default_download_path))
        self.folder_button = ctk.CTkButton(
            url_row,
            text="📁",
            width=ROW_HEIGHT,
            height=ROW_HEIGHT,
            font=DEFAULT_FONT,
            fg_color=ACCENT_COLOR,
            command=self.choose_folder
        )
        self.folder_button.pack(side="left", padx=(0, 0), pady=0)

        # Progress bar (same width as url_row)
        self.progress = ctk.CTkProgressBar(self, width=408, height=8, progress_color=ACCENT_COLOR)
        self.progress.set(0)
        self.progress.pack(padx=24, pady=(14, 0))

        # Remove status label and add filename entry (hidden by default)
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", padx=24, pady=(8, 0))

        self.filename_var = ctk.StringVar()
        self.filename_entry = ctk.CTkEntry(
            status_row,
            textvariable=self.filename_var,
            width=270,
            height=26,
            font=DEFAULT_FONT,
            fg_color="transparent",      # Fondo transparente
            border_width=0,              # Sin borde
            placeholder_text="",         # Sin placeholder
            text_color="#bbbbbb"         # Gris claro
        )
        # Do NOT pack yet (hidden by default)

        self.download_button = ctk.CTkButton(
            status_row, text="Descargar", width=124, height=ROW_HEIGHT, font=DEFAULT_FONT,
            fg_color=ACCENT_COLOR, command=self.start_download
        )
        self.download_button.pack(side="right", padx=(0, 0))

        self.cancel_button = ctk.CTkButton(
            status_row, text="🚫", width=ROW_HEIGHT, height=ROW_HEIGHT, font=("Segoe UI", 15, "bold"),
            fg_color="#888888", command=self.cancel_download, state="disabled"
        )
        # Do NOT pack yet

        self.url_entry.focus_set()
        self.url_var.trace_add("write", self.on_url_change)

    def on_url_change(self, *args):
        url = self.url_var.get().strip()
        if url:
            # Try to get filename from yt-dlp (info extraction, no download)
            filename = self.get_filename_from_url(url)
            self.filename_var.set(filename)
            if not hasattr(self, "_filename_entry_packed") or not self._filename_entry_packed:
                self.filename_entry.pack(side="left", padx=(0, 8), pady=0)
                self._filename_entry_packed = True
        else:
            self.filename_entry.pack_forget()
            self._filename_entry_packed = False

    def get_filename_from_url(self, url):
        # Siempre usar el formato por defecto, ignorando el título del video
        now = datetime.datetime.now()
        # Detecta la extensión según el formato seleccionado
        selected_format = self.format_var.get().upper() if hasattr(self, "format_var") else "MP4"
        ext_map = {
            "MP4": ".mp4",
            "WEBM": ".webm",
            "MP3": ".mp3",
            "OGG": ".ogg"
        }
        ext = ext_map.get(selected_format, ".mp4")
        return now.strftime(f"DownMasivo_%d_%m_%Y_%H_%M_%S{ext}")

    def on_format_change(self, event=None):
        config["last_format"] = self.format_var.get()
        save_config(config)

    def choose_folder(self):
        selected = ctk.filedialog.askdirectory(initialdir=self.folder_var.get())
        if selected:
            self.folder_var.set(selected)
            config["download_dir"] = selected
            save_config(config)

    def reset_ui_after_delay(self, delay=2500):
        def clear_ui():
            self.url_var.set("")
            self.progress.set(0)
        self.after(delay, clear_ui)

    def start_download(self):
        url = self.url_var.get().strip()
        selected_format = self.format_var.get().upper()
        download_dir = self.folder_var.get()
        filename = self.filename_var.get().strip()

        # Ensure filename has the correct extension
        ext_map = {
            "MP4": ".mp4",
            "WEBM": ".webm",
            "MP3": ".mp3",
            "OGG": ".ogg"
        }
        ext = ext_map.get(selected_format, ".mp4")
        if not filename.lower().endswith(ext):
            filename += ext

        config["last_format"] = self.format_var.get()
        config["download_dir"] = download_dir
        save_config(config)
        if not url:
            return

        # Hide filename entry
        self.filename_entry.pack_forget()
        self._filename_entry_packed = False

        self.cancel_flag = False
        self.cancel_button.pack(side="right", padx=(0, 8))
        self.cancel_button.configure(state="normal")
        self.download_button.configure(state="disabled")
        self.download_thread = threading.Thread(
            target=self.download_video,
            args=(url, selected_format, filename),
            daemon=True
        )
        self.download_thread.start()

    def cancel_download(self):
        self.cancel_flag = True
        self.cancel_button.configure(state="disabled")
        self.cancel_button.pack_forget()
        if self._ydl_instance is not None:
            try:
                self._ydl_instance.raise_interrupt()
            except Exception:
                pass

    def download_video(self, url, selected_format, filename):
        try:
            download_dir = self.folder_var.get()
            os.makedirs(download_dir, exist_ok=True)
            ffmpeg_path = get_ffmpeg_path()

            # --- Format selection logic ---
            if selected_format == "MP4":
                ydl_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                merge_output_format = "mp4"
                postprocessors = []
            elif selected_format == "WEBM":
                ydl_format = "bestvideo+bestaudio/best"
                merge_output_format = None
                postprocessors = [{
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "webm"
                }]
            elif selected_format == "MP3":
                ydl_format = "bestaudio/best"
                merge_output_format = None
                postprocessors = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            elif selected_format == "OGG":
                ydl_format = "bestaudio/best"
                merge_output_format = None
                postprocessors = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "vorbis",
                    "preferredquality": "192",
                }]
            else:
                ydl_format = "best"
                merge_output_format = None
                postprocessors = []
            # --- End format selection logic ---

            ydl_opts = {
                "outtmpl": os.path.join(download_dir, filename),
                "format": ydl_format,
                "merge_output_format": merge_output_format,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": "cookies.txt" if any(site in url for site in ["instagram.com", "twitter.com"]) else None,
                "ffmpeg_location": os.path.dirname(ffmpeg_path),
                "postprocessors": postprocessors,
            }

            self._partial_filename = None

            def progress_hook(d):
                if d["status"] == "downloading":
                    total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
                    downloaded = d.get("downloaded_bytes", 0)
                    percent = int((downloaded / total_bytes) * 100)
                    self.progress.set(percent / 100)
                    if "filename" in d:
                        self._partial_filename = d["filename"]
                    if self.cancel_flag:
                        self._delete_partial_files()
                        raise yt_dlp.utils.DownloadCancelled()
                elif d["status"] == "finished":
                    self.progress.set(0.9)

            ydl_opts["progress_hooks"] = [progress_hook]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._ydl_instance = ydl
                try:
                    info_dict = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info_dict)
                except yt_dlp.utils.DownloadCancelled:
                    self._delete_partial_files()
                    self.download_button.configure(state="normal")
                    self.cancel_button.pack_forget()
                    self.progress.set(0)
                    return
                finally:
                    self._ydl_instance = None

                self.progress.set(1)
                self.download_button.configure(state="normal")
                self.cancel_button.pack_forget()
                self.reset_ui_after_delay()

        except Exception as e:
            self.download_button.configure(state="normal")
            self.cancel_button.pack_forget()

    def _delete_partial_files(self):
        if self._partial_filename:
            base = self._partial_filename
            if os.path.exists(base):
                try:
                    os.remove(base)
                except Exception:
                    pass
            patterns = [
                base + '*',
            ]
            for pattern in patterns:
                for f in glob.glob(pattern):
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except Exception:
                        pass

if __name__ == "__main__":
    app = VideoDownloaderApp()
    app.mainloop()