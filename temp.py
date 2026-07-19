import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import sys
import os

# Commands format based on user request
RESOLUTION_FORMATS = {
    "1080p": "bv*[height<=1080][ext=mp4][vcodec*=avc1]+ba[ext=m4a]/b[height<=1080][ext=mp4]",
    "720p": "bv*[height<=720][ext=mp4][vcodec*=avc1]+ba[ext=m4a]/b[height<=720][ext=mp4]",
    "480p": "bv*[height<=480][ext=mp4][vcodec*=avc1]+ba[ext=m4a]/b[height<=480][ext=mp4]",
    "Default (Best)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
}

class VideoDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("yt-dlp Video Downloader Prototype")
        self.root.geometry("650x700")
        
        # Set a slight padding for everything
        padding = {'padx': 10, 'pady': 10}
        
        # URL Input
        ttk.Label(root, text="Video URL:").grid(row=0, column=0, sticky="w", **padding)
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(root, textvariable=self.url_var, width=60)
        self.url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", **padding)

        # Download Directory
        ttk.Label(root, text="Save Folder:").grid(row=1, column=0, sticky="w", **padding)
        self.dir_var = tk.StringVar(value=os.getcwd())
        dir_frame = ttk.Frame(root)
        dir_frame.grid(row=1, column=1, columnspan=2, sticky="ew", **padding)
        self.dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var, width=45)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.dir_btn = ttk.Button(dir_frame, text="Browse", command=self.browse_folder)
        self.dir_btn.pack(side="left")

        # Resolution Selection
        ttk.Label(root, text="Resolution:").grid(row=2, column=0, sticky="w", **padding)
        self.res_var = tk.StringVar(value="720p")
        self.res_combobox = ttk.Combobox(root, textvariable=self.res_var, values=list(RESOLUTION_FORMATS.keys()), state="readonly")
        self.res_combobox.grid(row=2, column=1, sticky="w", **padding)

        # Cookies.txt Option (Fix for DPAPI / 429 / Bot Error)
        self.use_cookies_var = tk.BooleanVar(value=False)
        self.use_cookies_check = ttk.Checkbutton(root, text="Use cookies.txt (Fixes DPAPI Encryption / Bot Errors)", variable=self.use_cookies_var)
        self.use_cookies_check.grid(row=3, column=1, sticky="w", padx=10, pady=5)
        
        ttk.Label(root, text="Cookies.txt File:").grid(row=4, column=0, sticky="e", padx=10, pady=5)
        self.cookie_file_var = tk.StringVar()
        cookie_frame = ttk.Frame(root)
        cookie_frame.grid(row=4, column=1, columnspan=2, sticky="ew", padx=10, pady=5)
        self.cookie_entry = ttk.Entry(cookie_frame, textvariable=self.cookie_file_var, width=40)
        self.cookie_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.cookie_btn = ttk.Button(cookie_frame, text="Browse", command=self.browse_cookie_file)
        self.cookie_btn.pack(side="left")

        ttk.Label(root, text="OR Paste Cookies:").grid(row=5, column=0, sticky="ne", padx=10, pady=5)
        self.cookie_text = tk.Text(root, height=5, width=60)
        self.cookie_text.grid(row=5, column=1, columnspan=2, sticky="ew", padx=10, pady=5)

        # Output Console
        ttk.Label(root, text="Console Output:").grid(row=6, column=0, sticky="nw", **padding)
        self.log_text = tk.Text(root, height=12, width=70, state="disabled")
        self.log_text.grid(row=7, column=0, columnspan=3, **padding)

        # Download Button
        self.download_btn = ttk.Button(root, text="Download Video", command=self.start_download)
        self.download_btn.grid(row=8, column=1, pady=10)

        root.grid_columnconfigure(1, weight=1)

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def browse_folder(self):
        folder_selected = filedialog.askdirectory(initialdir=self.dir_var.get())
        if folder_selected:
            self.dir_var.set(folder_selected)

    def browse_cookie_file(self):
        file_selected = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if file_selected:
            self.cookie_file_var.set(file_selected)

    def start_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a valid URL.")
            return

        res = self.res_var.get()
        format_str = RESOLUTION_FORMATS.get(res, RESOLUTION_FORMATS["720p"])

        # Construct Command
        cmd = ["yt-dlp", "--js-runtimes", "node", "-f", format_str, "--merge-output-format", "mp4"]
        
        download_dir = self.dir_var.get().strip()
        if download_dir:
            cmd.extend(["-P", download_dir])
            
        # Attach cookies option to avoid bot detection/429 errors
        if self.use_cookies_var.get():
            cookie_file = self.cookie_file_var.get().strip()
            pasted_cookies = self.cookie_text.get("1.0", tk.END).strip()
            
            if pasted_cookies:
                # Save pasted cookies to a temporary file
                temp_cookie_path = os.path.join(os.getcwd(), "temp_cookies.txt")
                with open(temp_cookie_path, "w", encoding="utf-8") as f:
                    f.write(pasted_cookies)
                cmd.extend(["--cookies", temp_cookie_path])
                self.log("Using pasted cookies.")
            elif cookie_file and os.path.exists(cookie_file):
                cmd.extend(["--cookies", cookie_file])
                self.log("Using selected cookie file.")
            else:
                self.log("⚠️ Cookies requested but neither valid file nor pasted content found. Trying without.")
            
        cmd.append(url)

        self.log("="*50)
        self.log(f"Starting download for: {url}")
        self.log(f"Resolution: {res}")
        self.log(f"Command executed: {' '.join(cmd)}")
        self.log("="*50 + "\n")
        
        self.download_btn.config(state="disabled")
        
        # Run in thread so the GUI does not freeze
        threading.Thread(target=self.run_download, args=(cmd,), daemon=True).start()

    def run_download(self, cmd):
        try:
            # We use CREATE_NO_WINDOW on Windows to prevent standard console popup
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags
            )

            # Read output line by line and print it to the GUI text box
            for line in iter(process.stdout.readline, ''):
                self.root.after(0, self.log, line.strip())
                
            process.stdout.close()
            return_code = process.wait()

            if return_code == 0:
                self.root.after(0, self.log, "\n✅ Download Completed Successfully!")
            else:
                self.root.after(0, self.log, f"\n❌ Download failed with return code: {return_code}")
                
        except Exception as e:
            self.root.after(0, self.log, f"❌ Error starting download: {str(e)}\nMake sure yt-dlp and node are installed and available in PATH.")
            
        finally:
            self.root.after(0, lambda: self.download_btn.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoDownloaderGUI(root)
    root.mainloop()
