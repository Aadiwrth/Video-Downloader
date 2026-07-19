import subprocess
import threading
import sys
import os
import re
import shlex

class YTDlpDownloader:
    def __init__(self):
        # Regex patterns to parse progress percentage, download speed, and ETA from yt-dlp stdout
        self.percent_pattern = re.compile(r'\[download\]\s+([\d\.]+)\%')
        self.speed_pattern = re.compile(r'at\s+([0-9\.]+\S+)')
        self.eta_pattern = re.compile(r'ETA\s+(\S+)')
        self.dest_pattern = re.compile(r'\[download\] Destination: (.*)')
        self.current_process = None
        self.is_cancelled = False
        self.is_paused = False
        self.current_files = []

    def cancel_download(self):
        self.is_cancelled = True
        if self.current_process:
            try:
                self.current_process.terminate()
            except:
                pass
                
    def pause_download(self):
        self.is_paused = True
        if self.current_process:
            try:
                self.current_process.terminate()
            except:
                pass

    def start_download(self, url, format_str, output_dir, custom_title, use_cookies, cookie_file, pasted_cookies, proxy_url, extract_audio, download_playlist, use_aria2, custom_args, overwrite_defaults, progress_callback, log_callback, completion_callback):
        self.is_cancelled = False
        self.is_paused = False
        self.current_files = []
        # We run this in a thread so it doesn't block the GUI main loop
        thread = threading.Thread(
            target=self._download_thread,
            args=(url, format_str, output_dir, custom_title, use_cookies, cookie_file, pasted_cookies, proxy_url, extract_audio, download_playlist, use_aria2, custom_args, overwrite_defaults, progress_callback, log_callback, completion_callback),
            daemon=True
        )
        thread.start()

    def inspect_media(self, url, use_cookies, cookie_file, pasted_cookies, proxy_url, callback):
        thread = threading.Thread(
            target=self._inspect_thread,
            args=(url, use_cookies, cookie_file, pasted_cookies, proxy_url, callback),
            daemon=True
        )
        thread.start()

    def _inspect_thread(self, url, use_cookies, cookie_file, pasted_cookies, proxy_url, callback):
        # We add --js-runtimes node to solve the YouTube signature decryption challenge (n-challenge)
        cmd = ["yt-dlp", "--dump-json", "--no-playlist", "--js-runtimes", "node"]
        if proxy_url:
            cmd.extend(["--proxy", proxy_url])
            
        temp_cookie_path = None
        try:
            if use_cookies:
                if pasted_cookies:
                    import uuid
                    temp_cookie_path = os.path.join(os.getcwd(), f"temp_cookies_inspect_{uuid.uuid4().hex}.txt")
                    with open(temp_cookie_path, "w", encoding="utf-8") as f:
                        f.write(pasted_cookies)
                    cmd.extend(["--cookies", temp_cookie_path])
                elif cookie_file and os.path.exists(cookie_file):
                    cmd.extend(["--cookies", cookie_file])
                    
            cmd.append(url)
            
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                creationflags=creationflags
            )
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                import json
                info = json.loads(stdout)
                title = info.get("title", "Unknown Title")
                formats = info.get("formats", [])
                
                # Extract unique video heights
                heights = set()
                for f in formats:
                    height = f.get("height")
                    if height and f.get("vcodec") != "none":
                        heights.add(int(height))
                
                callback({"success": True, "title": title, "resolutions": sorted(list(heights), reverse=True)})
            else:
                callback({"success": False, "error": stderr.strip() or "Failed to retrieve metadata."})
        except Exception as e:
            callback({"success": False, "error": str(e)})
        finally:
            if temp_cookie_path and os.path.exists(temp_cookie_path):
                try:
                    os.remove(temp_cookie_path)
                except:
                    pass

    def _download_thread(self, url, format_str, output_dir, custom_title, use_cookies, cookie_file, pasted_cookies, proxy_url, extract_audio, download_playlist, use_aria2, custom_args, overwrite_defaults, progress_callback, log_callback, completion_callback):
        cmd = ["yt-dlp", "--newline", "--js-runtimes", "node", "-f", format_str]
        
        if not overwrite_defaults:
            # We use --concurrent-fragments 5 to speed up Dash/HLS segment downloading natively
            cmd.extend(["--hls-prefer-native", "--embed-metadata", "--concurrent-fragments", "5"])
            if extract_audio:
                cmd.extend(["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"])
                cmd.extend(["--embed-thumbnail"]) # For MP3s, embedding thumbnail usually sets the album art correctly
            else:
                # We use --merge-output-format instead of remux to keep progressive MP4s fully intact
                cmd.extend(["--merge-output-format", "mp4"])
                # Mutagen can safely embed the thumbnail without breaking Windows Media Player MP4s
                cmd.extend(["--embed-thumbnail", "--convert-thumbnails", "jpg"])
                
        if custom_args:
            try:
                parsed_args = shlex.split(custom_args)
                cmd.extend(parsed_args)
            except Exception as e:
                log_callback(f"⚠️ Error parsing custom arguments: {str(e)}. Splitting by space.")
                cmd.extend(custom_args.split())
            
        if download_playlist:
            cmd.append("--yes-playlist")
        else:
            cmd.append("--no-playlist")
            
        if use_aria2:
            cmd.extend(["--external-downloader", "aria2c", "--external-downloader-args", "aria2c:-j 16 -x 16 -s 16 -k 1M"])

        if custom_title:
            if download_playlist:
                cmd.extend(["-o", f"{custom_title} - %(playlist_index)03d - %(title)s.%(ext)s"])
            else:
                cmd.extend(["-o", f"{custom_title}.%(ext)s"])
        
        if output_dir:
            cmd.extend(["-P", output_dir])
            
        if proxy_url:
            cmd.extend(["--proxy", proxy_url])
            
        temp_cookie_path = None
        try:
            if use_cookies:
                if pasted_cookies:
                    import uuid
                    temp_cookie_path = os.path.join(os.getcwd(), f"temp_cookies_{uuid.uuid4().hex}.txt")
                    with open(temp_cookie_path, "w", encoding="utf-8") as f:
                        f.write(pasted_cookies)
                    cmd.extend(["--cookies", temp_cookie_path])
                    log_callback("Using pasted cookies.")
                elif cookie_file and os.path.exists(cookie_file):
                    cmd.extend(["--cookies", cookie_file])
                    log_callback("Using selected cookie file.")
                else:
                    log_callback("⚠️ Cookies requested but neither valid file nor pasted content found. Trying without.")
            
            cmd.append(url)
            log_callback(f"Executing: {' '.join(cmd)}")
            
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                creationflags=creationflags
            )

            for line in iter(self.current_process.stdout.readline, ''):
                if self.is_cancelled or self.is_paused:
                    break
                line = line.strip()
                
                dest_match = self.dest_pattern.search(line)
                if dest_match:
                    self.current_files.append(dest_match.group(1).strip())
                    
                # Extract progress percentage, speed, and ETA to update GUI
                percent_match = self.percent_pattern.search(line)
                if percent_match:
                    try:
                        percent_float = float(percent_match.group(1)) / 100.0
                        
                        speed_match = self.speed_pattern.search(line)
                        eta_match = self.eta_pattern.search(line)
                        
                        speed_str = speed_match.group(1) if speed_match else "N/A"
                        eta_str = eta_match.group(1) if eta_match else "N/A"
                        
                        progress_callback(percent_float, speed_str, eta_str)
                    except:
                        pass
                
                log_callback(line)
                
            self.current_process.stdout.close()
            return_code = self.current_process.wait()

            if self.is_paused:
                log_callback("\n⏸️ Download Paused. You can resume later.")
                completion_callback("PAUSED")
            elif self.is_cancelled:
                log_callback("\n⚠️ Download cancelled. Cleaning up temporary files...")
                for file_path in self.current_files:
                    for ext in ["", ".part", ".ytdl"]:
                        try:
                            target = file_path + ext
                            if os.path.exists(target):
                                os.remove(target)
                        except:
                            pass
                completion_callback("CANCELLED")
            elif return_code == 0:
                log_callback("\n✅ Download Completed Successfully!")
                completion_callback(True)
            else:
                log_callback(f"\n❌ Download failed with return code: {return_code}")
                completion_callback(False)
                
        except Exception as e:
            log_callback(f"❌ Error starting download: {str(e)}")
            completion_callback(False)
        finally:
            if temp_cookie_path and os.path.exists(temp_cookie_path):
                try:
                    os.remove(temp_cookie_path)
                except:
                    pass
