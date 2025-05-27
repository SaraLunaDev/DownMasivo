import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import sys
import os
import subprocess
import yt_dlp
from pathlib import Path

CONFIG_FILE = "config.json"
DEFAULT_FONT = ("Segoe UI", 10)
ACCENT_COLOR = "#4a6fa5"
DARK_BG = "#f0f0f0"
LIGHT_BG = "#ffffff"

default_download_path = str(Path.home() / "Downloads")
default_config = {
    "download_dir": default_download_path,
    "convert_to_webm": False
}

def get_ffmpeg_path():
    import sys, os
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        return os.path.join(base_path, "ffmpeg", "ffmpeg.exe")
    else:
        return "ffmpeg"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return default_config.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

config = load_config()

class VideoDownloaderApp:
    def __init__(self, root):
        self.cancel_flag = False
        self.download_thread = None
        self.conversion_thread = None
        self.root = root
        self.root.title("DownMasivo")
        self.root.geometry("500x180")
        self.root.resizable(False, False)
        self.root.configure(bg=DARK_BG)

        try:
            import sys, os
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base_path, "icono.ico")
            self.root.iconbitmap(icon_path)
        except Exception as e:
            pass

        self.style = ttk.Style()
        self.style.theme_use('alt')
        self.style.configure('TFrame', background=DARK_BG)
        self.style.configure('TLabel', background=DARK_BG, font=DEFAULT_FONT)
        self.style.configure('TButton', font=DEFAULT_FONT, background=ACCENT_COLOR, 
                           foreground='white', borderwidth=1)
        self.style.map('TButton', 
                      background=[('active', '#3a5a8f'), ('pressed', '#2a4a7f')])
        self.style.configure('TEntry', fieldbackground=LIGHT_BG, font=DEFAULT_FONT)
        self.style.configure('TCheckbutton', background=DARK_BG, font=DEFAULT_FONT)
        self.style.configure('Horizontal.TProgressbar', thickness=10, troughcolor=DARK_BG, 
                            background=ACCENT_COLOR, lightcolor=ACCENT_COLOR, 
                            darkcolor=ACCENT_COLOR)

        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.title_frame = ttk.Frame(self.main_frame)
        self.title_frame.pack(fill=tk.X, pady=(0, 10))

        self.settings_button = ttk.Button(self.title_frame, text="⚙", width=3, command=self.open_config_window)
        self.settings_button.pack(side=tk.LEFT, padx=(0, 8))

        self.title_label = ttk.Label(self.title_frame, text="DownMasivo", 
                                    font=("Segoe UI", 16, "bold"), foreground=ACCENT_COLOR)
        self.title_label.pack(side=tk.LEFT)

        self.subtitle_label = ttk.Label(self.title_frame, text="jeje god",
                                        font=("Segoe UI", 12), foreground="#888888")
        self.subtitle_label.pack(side=tk.LEFT, padx=(10, 0))

        self.url_frame = ttk.Frame(self.main_frame)
        self.url_frame.pack(fill=tk.X, pady=5)
        
        self.url_label = ttk.Label(self.url_frame, text="URL:")
        self.url_label.pack(side=tk.LEFT, padx=(0, 8))
        
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(self.url_frame, textvariable=self.url_var, width=40)
        self.url_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.progress = ttk.Progressbar(self.main_frame, orient="horizontal", 
                                      length=300, mode="determinate")
        self.progress.pack(pady=(6,4), fill=tk.X)

        self.status_label = ttk.Label(self.main_frame, text="Listo", 
                                      font=("Segoe UI", 9), foreground="#666666", anchor="w")
        self.status_label.pack(fill=tk.X, pady=(5)) 

        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(fill=tk.X, pady=4)

        self.download_button = ttk.Button(self.button_frame, text="Descargar", command=self.start_download)
        self.download_button.pack(side=tk.RIGHT, padx=(5, 0))

        self.cancel_button = ttk.Button(self.button_frame, text="X", width=3, state="disabled", command=self.cancel_download)
        self.cancel_button.pack(side=tk.RIGHT, padx=(0, 5))

        self.url_entry.focus_set()

    def reset_ui_after_delay(self, delay=3000):
        def clear_ui():
            self.url_var.set("")
            self.progress["value"] = 0
            self.status_label.config(text="Listo", foreground="#666666")
        self.root.after(delay, clear_ui)

    def start_download(self):
        url = self.url_var.get().strip()
        if not url:
            self.status_label.config(text="Por favor ingresa una URL.", foreground="red")
            return

        self.cancel_flag = False
        self.cancel_button.config(state="normal")
        self.download_button.config(state="disabled")
        self.status_label.config(text="Iniciando descarga...", foreground=ACCENT_COLOR)
        self.download_thread = threading.Thread(
            target=self.download_video, 
            args=(url,),
            daemon=True
        )
        self.download_thread.start()

    def cancel_download(self):
        self.cancel_flag = True
        self.status_label.config(text="Cancelando...", foreground="orange")
        self.cancel_button.config(state="disabled")

    def download_video(self, url):
        try:
            download_dir = config["download_dir"]
            os.makedirs(download_dir, exist_ok=True)

            ffmpeg_path = get_ffmpeg_path()

            ydl_opts = {
                "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
                "progress_hooks": [self.update_progress_hook],
                "quiet": True,
                "no_warnings": True,
                "cookiefile": "cookies.txt" if any(site in url for site in ["instagram.com", "twitter.com"]) else None,
                "ffmpeg_location": ffmpeg_path,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info_dict)
                
                if self.cancel_flag:
                    self.status_label.config(text="Download cancelled.", foreground="orange")
                    try:
                        if os.path.exists(filename):
                            os.remove(filename)
                    except:
                        pass
                    return
                
                if config["convert_to_webm"]:
                    self.conversion_thread = threading.Thread(
                        target=self.convert_to_webm,
                        args=(filename,),
                        daemon=True
                    )
                    self.conversion_thread.start()
                else:
                    self.progress["value"] = 100
                    self.status_label.config(text="Download complete!", foreground="green")
                    self.download_button.config(state="normal")
                    self.cancel_button.config(state="disabled")
                    self.reset_ui_after_delay()
                
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", foreground="red")
            self.download_button.config(state="normal")
            self.cancel_button.config(state="disabled")

    def convert_to_webm(self, filename):
        if not filename.lower().endswith(".mp4"):
            return

        try:
            self.root.after(0, lambda: [
                self.status_label.config(
                    text="Converting to WebM...", 
                    foreground=ACCENT_COLOR
                ),
                self.progress.config(value=90)
            ])

            webm_path = os.path.splitext(filename)[0] + ".webm"

            if os.path.exists(webm_path):
                os.remove(webm_path)

            ffmpeg_path = get_ffmpeg_path()

            command = [
                ffmpeg_path,
                "-i", filename,
                "-c:v", "libvpx-vp9",
                "-crf", "30",
                "-b:v", "0",
                "-c:a", "libopus",
                "-b:a", "128k",
                "-progress", "pipe:1",
                webm_path
            ]

            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                creationflags=creationflags
            )

            while True:
                if self.cancel_flag:
                    process.terminate()
                    try:
                        if os.path.exists(webm_path):
                            os.remove(webm_path)
                    except:
                        pass
                    self.root.after(0, lambda: self.status_label.config(
                        text="Conversion cancelled", 
                        foreground="orange"
                    ))
                    break
                    
                line = process.stdout.readline()
                if not line:
                    break
                    
                if "out_time_ms=" in line:
                    time_ms = line.split("=")[1].strip()
                    try:
                        progress = min(90 + int(int(time_ms) / 1000000), 99)
                        self.root.after(0, lambda v=progress: [
                            self.progress.config(value=v),
                            self.status_label.config(
                                text=f"Converting to WebM... {v-90}%", 
                                foreground=ACCENT_COLOR
                            )
                        ])
                    except:
                        pass
                        
            return_code = process.wait()
            
            if return_code == 0 and os.path.exists(webm_path):
                try:
                    os.remove(filename)
                except:
                    pass
                    
                self.root.after(0, lambda: [
                    self.progress.config(value=100),
                    self.status_label.config(
                        text="WebM conversion complete!", 
                        foreground="green"
                    ),
                    self.download_button.config(state="normal"),
                    self.cancel_button.config(state="disabled")
                ])
            else:
                self.root.after(0, lambda: [
                    self.status_label.config(
                        text="MP4 saved (WebM conversion failed)", 
                        foreground="orange"
                    ),
                    self.download_button.config(state="normal"),
                    self.cancel_button.config(state="disabled")
                ])
                
        except Exception as e:
            self.root.after(0, lambda: [
                self.status_label.config(
                    text=f"MP4 saved (Error: {str(e)})", 
                    foreground="orange"
                ),
                self.download_button.config(state="normal"),
                self.cancel_button.config(state="disabled")
            ])

    def update_progress_hook(self, d):
        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
            downloaded = d.get("downloaded_bytes", 0)
            percent = int((downloaded / total_bytes) * 100)
            self.progress["value"] = percent
            self.status_label.config(text=f"Descargando... {percent}%", foreground=ACCENT_COLOR)
        elif d["status"] == "finished":
            self.progress["value"] = 90
            self.status_label.config(text="Descarga completada, preparando conversión...", foreground=ACCENT_COLOR)

    def open_config_window(self):
        cfg_win = tk.Toplevel(self.root)
        cfg_win.title("Configuración")
        cfg_win.geometry("400x180")
        cfg_win.configure(bg=DARK_BG)
        cfg_win.resizable(False, False)

        cfg_frame = ttk.Frame(cfg_win, padding="10")
        cfg_frame.pack(fill=tk.BOTH, expand=True)

        self.webm_var = tk.BooleanVar(value=config.get("convert_to_webm", False))
        webm_toggle = ttk.Checkbutton(
            cfg_frame, 
            text="Convertir a WebM después de descargar",
            variable=self.webm_var
        )
        webm_toggle.pack(anchor=tk.W, pady=(0, 15))

        ttk.Label(cfg_frame, text="Carpeta de descarga:").pack(anchor=tk.W, pady=(0, 5))

        folder_frame = ttk.Frame(cfg_frame)
        folder_frame.pack(fill=tk.X, pady=(0, 15))

        self.folder_var = tk.StringVar(value=config.get("download_dir", default_download_path))
        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, state="readonly")
        folder_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        def choose_folder():
            selected = filedialog.askdirectory(initialdir=self.folder_var.get())
            if selected:
                self.folder_var.set(selected)

        ttk.Button(folder_frame, text="Buscar", command=choose_folder).pack(side=tk.LEFT)

        def save_changes():
            if not os.path.isdir(self.folder_var.get()):
                messagebox.showerror("Error", "Directorio de descarga inválido")
                return
                
            config["download_dir"] = self.folder_var.get()
            config["convert_to_webm"] = self.webm_var.get()
            save_config(config)
            cfg_win.destroy()

        ttk.Button(cfg_frame, text="Guardar configuración", command=save_changes).pack(pady=(20, 0))

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoDownloaderApp(root)
    root.mainloop()