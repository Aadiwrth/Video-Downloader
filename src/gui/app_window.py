import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from core.downloader import YTDlpDownloader

# Force exact string match for '1080p', '720p', '480p' to catch direct HTTP MP4s (like on PH)
# and avoid HLS streams entirely. Falls back to best or separated streams for YouTube.
RESOLUTION_FORMATS = {
    "1080p": "1080p/best[height<=1080][ext=mp4]/bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]",
    "720p": "720p/best[height<=720][ext=mp4]/bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
    "480p": "480p/best[height<=480][ext=mp4]/bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]",
    "Default (Best)": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
}

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Pro Video Downloader - yt-dlp")
        self.geometry("750x950")
        
        # Modern Look settings
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        self.downloader = YTDlpDownloader()
        
        self._build_ui()

    def _build_ui(self):
        # Title Label
        self.title_label = ctk.CTkLabel(self, text="yt-dlp GUI Video Downloader", font=ctk.CTkFont(size=26, weight="bold"))
        self.title_label.pack(pady=(20, 10))
        
        # Main Frame with rounded corners
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        # --- URL INPUT ---
        self.url_label = ctk.CTkLabel(self.main_frame, text="Video URL:", font=ctk.CTkFont(weight="bold"))
        self.url_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(self.main_frame, textvariable=self.url_var, width=450, placeholder_text="https://www.youtube.com/watch?v=...", border_width=2)
        self.url_entry.grid(row=0, column=1, padx=20, pady=(20, 10), sticky="w")
        
        # --- SAVE FOLDER ---
        self.folder_label = ctk.CTkLabel(self.main_frame, text="Save Folder:", font=ctk.CTkFont(weight="bold"))
        self.folder_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.dir_var = ctk.StringVar(value=os.getcwd())
        
        self.dir_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.dir_frame.grid(row=1, column=1, padx=20, pady=10, sticky="w")
        
        self.dir_entry = ctk.CTkEntry(self.dir_frame, textvariable=self.dir_var, width=340)
        self.dir_entry.pack(side="left", padx=(0, 10))
        self.dir_btn = ctk.CTkButton(self.dir_frame, text="Browse", width=100, command=self._browse_folder)
        self.dir_btn.pack(side="left")
        
        # --- RESOLUTION ---
        self.res_label = ctk.CTkLabel(self.main_frame, text="Resolution:", font=ctk.CTkFont(weight="bold"))
        self.res_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        
        self.res_var = ctk.StringVar(value="720p")
        self.res_combo = ctk.CTkComboBox(self.main_frame, variable=self.res_var, values=list(RESOLUTION_FORMATS.keys()), width=200, state="readonly")
        self.res_combo.grid(row=2, column=1, padx=20, pady=10, sticky="w")
        
        # --- COOKIES SECTION ---
        self.cookies_switch_var = ctk.BooleanVar(value=False)
        self.cookies_switch = ctk.CTkSwitch(self.main_frame, text="Use Netscape Cookies (Fixes Bot & DPAPI Errors)", variable=self.cookies_switch_var, font=ctk.CTkFont(weight="bold"))
        self.cookies_switch.grid(row=3, column=1, padx=20, pady=15, sticky="w")
        
        self.cookie_file_label = ctk.CTkLabel(self.main_frame, text="Cookies File:")
        self.cookie_file_label.grid(row=4, column=0, padx=20, pady=5, sticky="w")
        
        self.cookie_file_var = ctk.StringVar()
        self.cookie_file_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.cookie_file_frame.grid(row=4, column=1, padx=20, pady=5, sticky="w")
        
        self.cookie_entry = ctk.CTkEntry(self.cookie_file_frame, textvariable=self.cookie_file_var, width=340, placeholder_text="Path to cookies.txt")
        self.cookie_entry.pack(side="left", padx=(0, 10))
        self.cookie_btn = ctk.CTkButton(self.cookie_file_frame, text="Browse", width=100, command=self._browse_cookie_file)
        self.cookie_btn.pack(side="left")
        
        self.cookie_paste_label = ctk.CTkLabel(self.main_frame, text="OR Paste Cookies:")
        self.cookie_paste_label.grid(row=5, column=0, padx=20, pady=5, sticky="nw")
        
        self.cookie_textbox = ctk.CTkTextbox(self.main_frame, width=450, height=80, border_width=1)
        self.cookie_textbox.grid(row=5, column=1, padx=20, pady=5, sticky="w")
        
        # --- PROXY ---
        self.proxy_label = ctk.CTkLabel(self.main_frame, text="Proxy (Optional):", font=ctk.CTkFont(weight="bold"))
        self.proxy_label.grid(row=6, column=0, padx=20, pady=10, sticky="w")
        
        self.proxy_var = ctk.StringVar()
        self.proxy_entry = ctk.CTkEntry(self.main_frame, textvariable=self.proxy_var, width=450, placeholder_text="e.g. http://127.0.0.1:1080 or socks5://...", border_width=1)
        self.proxy_entry.grid(row=6, column=1, padx=20, pady=10, sticky="w")
        
        # --- ACTION BUTTONS ---
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.grid(row=7, column=0, columnspan=2, pady=(20, 10))
        
        self.download_btn = ctk.CTkButton(self.button_frame, text="Start Download", font=ctk.CTkFont(weight="bold", size=15), height=45, fg_color="#1f6aa5", hover_color="#144870", command=self._start_download)
        self.download_btn.pack(side="left", padx=10)
        
        self.pause_btn = ctk.CTkButton(self.button_frame, text="Pause", font=ctk.CTkFont(weight="bold", size=15), height=45, fg_color="#a57a1f", hover_color="#705314", command=self._pause_download, state="disabled")
        self.pause_btn.pack(side="left", padx=10)
        
        self.cancel_btn = ctk.CTkButton(self.button_frame, text="Cancel", font=ctk.CTkFont(weight="bold", size=15), height=45, fg_color="#a51f1f", hover_color="#701414", command=self._cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=10)
        
        # --- PROGRESS BAR ---
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=600, height=12)
        self.progress_bar.grid(row=8, column=0, columnspan=2, padx=20, pady=(10, 10))
        self.progress_bar.set(0)
        
        # --- CONSOLE LOG ---
        self.log_textbox = ctk.CTkTextbox(self.main_frame, width=600, height=180, state="disabled", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_textbox.grid(row=9, column=0, columnspan=2, padx=20, pady=10)
        
    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dir_var.get())
        if folder:
            self.dir_var.set(folder)
            
    def _browse_cookie_file(self):
        file = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if file:
            self.cookie_file_var.set(file)
            
    def _cancel_download(self):
        self.downloader.cancel_download()
        self.cancel_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled")
        self.download_btn.configure(state="normal", text="Start Download")
        self.progress_bar.set(0)
        
    def _pause_download(self):
        self.downloader.pause_download()
        self.pause_btn.configure(state="disabled")
        
    def _append_log(self, msg):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", msg + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        
    def _update_progress(self, value):
        self.progress_bar.set(value)
        
    def _on_download_complete(self, status):
        self.download_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled")
        
        if status == True:
            self.download_btn.configure(text="Start Download")
            self.progress_bar.set(1.0)
            messagebox.showinfo("Success", "Video downloaded successfully!")
        elif status == "PAUSED":
            self.download_btn.configure(text="Resume")
            self.cancel_btn.configure(state="normal")
        elif status == "CANCELLED":
            self.download_btn.configure(text="Start Download")
            self.progress_bar.set(0)
            messagebox.showinfo("Cancelled", "Download cancelled and files cleaned up.")
        else:
            self.download_btn.configure(text="Start Download")
            messagebox.showerror("Error", "Download failed. Check the logs for details.")

    def _start_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a valid URL.")
            return
            
        # Clear logs
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        
        format_str = RESOLUTION_FORMATS.get(self.res_var.get(), RESOLUTION_FORMATS["720p"])
        output_dir = self.dir_var.get().strip()
        use_cookies = self.cookies_switch_var.get()
        cookie_file = self.cookie_file_var.get().strip()
        pasted_cookies = self.cookie_textbox.get("1.0", "end").strip()
        proxy_url = self.proxy_var.get().strip()
        
        # Wrappers to marshal thread updates to the main GUI thread safely
        def safe_log(msg):
            self.after(0, lambda: self._append_log(msg))
            
        def safe_progress(percent):
            self.after(0, lambda: self.progress_bar.set(percent))
            
        def safe_complete(success):
            self.after(0, self._on_download_complete, success)
        
        # Disable button during download
        self.download_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.cancel_btn.configure(state="normal")
        
        self.downloader.start_download(
            url=url,
            format_str=format_str,
            output_dir=output_dir,
            use_cookies=use_cookies,
            cookie_file=cookie_file,
            pasted_cookies=pasted_cookies,
            proxy_url=proxy_url,
            progress_callback=safe_progress,
            log_callback=safe_log,
            completion_callback=safe_complete
        )
