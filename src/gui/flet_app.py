import flet as ft
import os
import re
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from core.downloader import YTDlpDownloader

def get_format_string(selection, export_tv=False):
    if export_tv:
        if selection == "Default (Best)":
            return "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]/best"
        elif selection == "Audio Only (MP3)":
            return "bestaudio/best"
        
        match = re.search(r'(\d+)p', selection)
        if match:
            height = match.group(1)
            return f"bestvideo[vcodec^=avc1][height<={height}]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1][height<={height}]/best"
        return "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]/best"
    else:
        if selection == "Default (Best)":
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif selection == "Audio Only (MP3)":
            return "bestaudio/best"
        
        match = re.search(r'(\d+)p', selection)
        if match:
            height = match.group(1)
            return f"bv*[height<={height}][ext=mp4]+ba[ext=m4a]/{height}p/best[height<={height}][ext=mp4]/b[height<={height}]"
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

def run_flet_app():
    def main(page: ft.Page):
        page.title = "Video Downloader - yt-dlp"
        
        # Load persisted settings on startup
        initial_mode = page.client_storage.get("theme_mode") or "dark"
        page.theme_mode = ft.ThemeMode.LIGHT if initial_mode == "light" else ft.ThemeMode.DARK
        
        initial_theme_color = page.client_storage.get("theme_color") or "blue"
        theme_color_map = {
            "blue": ft.colors.BLUE_ACCENT,
            "purple": ft.colors.PURPLE_ACCENT,
            "green": ft.colors.GREEN_ACCENT,
            "orange": ft.colors.ORANGE_ACCENT,
            "red": ft.colors.RED_ACCENT,
            "teal": ft.colors.TEAL_ACCENT,
            "pink": ft.colors.PINK_ACCENT
        }
        accent_color = theme_color_map.get(initial_theme_color, ft.colors.BLUE_ACCENT)
        page.theme = ft.Theme(
            color_scheme_seed=accent_color,
            visual_density=ft.VisualDensity.COMFORTABLE
        )
        
        page.window.icon = "icon.ico"
        page.window.width = 850
        page.window.height = 950
        page.scroll = ft.ScrollMode.AUTO
        page.padding = 20
        
        downloader = YTDlpDownloader()
        
        # --- STATE ---
        state = {
            "queue": [],
            "is_running": False,
            "current_index": 0
        }
        
        # Define API callback to handle requests from the Chrome/Firefox extension
        def add_from_extension(url, title, resolution, grabbed_cookies=None):
            default_dir = page.client_storage.get("default_dir") or os.getcwd()
            # Check if we should use extension cookies
            use_ext_cookies = page.client_storage.get("use_extension_cookies") is not False
            export_tv = page.client_storage.get("export_tv") is True
            
            # If cookies were grabbed by the extension and extension cookies are enabled, prioritize them
            use_cookies = True if (grabbed_cookies and use_ext_cookies) else cookies_switch.value
            cookie_file = cookie_file_input.value.strip()
            pasted_cookies = grabbed_cookies if (grabbed_cookies and use_ext_cookies) else cookie_paste.value.strip()
            proxy_url = proxy_input.value.strip()
            use_aria2 = aria2_switch.value
            download_playlist = playlist_switch.value
            
            format_str = get_format_string(resolution, export_tv)
            
            # Load custom args from storage at the time of extension trigger
            custom_args = page.client_storage.get("custom_args") or ""
            overwrite_defaults = page.client_storage.get("custom_args_overwrite") is True
            
            # If TV compatibility is active and resolution height is > 1080p, print warning in logs
            height_match = re.search(r'(\d+)', resolution)
            if height_match and export_tv:
                h = int(height_match.group(1))
                if h > 1080:
                    append_log(f"⚠️ Warning: Added {resolution} video from extension with TV Compatibility enabled. Note that some TVs may fail to play resolutions higher than 1080p.")
            
            state["queue"].append({
                "url": url,
                "resolution": resolution,
                "format_str": format_str,
                "output_dir": default_dir,
                "custom_title": title,
                "use_cookies": use_cookies,
                "cookie_file": cookie_file,
                "pasted_cookies": pasted_cookies,
                "proxy_url": proxy_url,
                "extract_audio": (resolution == "Audio Only (MP3)"),
                "download_playlist": download_playlist,
                "use_aria2": use_aria2,
                "custom_args": custom_args,
                "overwrite_defaults": overwrite_defaults,
                "status": "Queued"
            })
            
            update_queue_ui()
            
            # Auto start downloader if queue is not active
            if not state["is_running"]:
                state["is_running"] = True
                process_next_queue_item()
                
            try:
                page.open(ft.SnackBar(ft.Text("Added link from browser extension!")))
            except:
                pass
                
            try:
                page.window_to_front()
            except:
                pass

        def inspect_from_extension(url, grabbed_cookies=None):
            # Check if we should ignore extension cookies
            use_ext_cookies = page.client_storage.get("use_extension_cookies") is not False
            if not use_ext_cookies:
                grabbed_cookies = None
                
            use_cookies = True if grabbed_cookies else cookies_switch.value
            cookie_file = cookie_file_input.value.strip()
            pasted_cookies = grabbed_cookies if grabbed_cookies else cookie_paste.value.strip()
            proxy_url = proxy_input.value.strip()
            
            event = threading.Event()
            inspect_result = {}
            
            def callback(res):
                nonlocal inspect_result
                inspect_result = res
                event.set()
                
            downloader.inspect_media(
                url=url,
                use_cookies=use_cookies,
                cookie_file=cookie_file,
                pasted_cookies=pasted_cookies,
                proxy_url=proxy_url,
                callback=callback
            )
            
            completed = event.wait(timeout=30.0)
            if not completed:
                return {
                    "success": False,
                    "error": "Inspection timed out",
                    "export_tv": page.client_storage.get("export_tv") is True
                }
                
            if isinstance(inspect_result, dict):
                inspect_result["export_tv"] = page.client_storage.get("export_tv") is True
                
            return inspect_result
            
        # Start Extension API Server in background thread
        class ExtensionAPIHandler(BaseHTTPRequestHandler):
            add_callback = None
            inspect_callback = None
            
            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()

            def do_POST(self):
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                # Setup response and CORS
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                try:
                    data = json.loads(post_data.decode('utf-8'))
                    url = data.get("url")
                    
                    if self.path == "/inspect":
                        cookies = data.get("cookies", "")
                        if ExtensionAPIHandler.inspect_callback and url:
                            res = ExtensionAPIHandler.inspect_callback(url, cookies)
                            self.wfile.write(json.dumps(res).encode('utf-8'))
                        else:
                            self.wfile.write(json.dumps({"success": False, "error": "Inspect callback unavailable"}).encode('utf-8'))
                            
                    elif self.path == "/add" or self.path == "/":
                        title = data.get("title", "")
                        resolution = data.get("resolution", "Default (Best)")
                        cookies = data.get("cookies", "")
                        
                        if url and ExtensionAPIHandler.add_callback:
                            ExtensionAPIHandler.add_callback(url, title, resolution, cookies)
                            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                        else:
                            self.wfile.write(json.dumps({"success": False, "error": "Add callback unavailable"}).encode('utf-8'))
                except Exception as e:
                    self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
                    
            def do_GET(self):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "running"}).encode('utf-8'))
                
            def log_message(self, format, *args):
                pass
                
        def run_api_server():
            ExtensionAPIHandler.add_callback = add_from_extension
            ExtensionAPIHandler.inspect_callback = inspect_from_extension
            try:
                server = HTTPServer(('127.0.0.1', 8283), ExtensionAPIHandler)
                server.serve_forever()
            except Exception as e:
                append_log(f"⚠️ Extension Link Server failed to start: {str(e)}")

        api_thread = threading.Thread(target=run_api_server, daemon=True)
        api_thread.start()
        
        # --- UI ELEMENTS ---
        speed_text = ft.Text("Speed: --", size=13, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200)
        eta_text = ft.Text("ETA: --", size=13, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200)
        
        logo_image = ft.Image(src="icon.png", width=44, height=44, fit=ft.ImageFit.CONTAIN)
        title_text = ft.Text("Video Downloader", size=24, weight=ft.FontWeight.BOLD)
        subtitle_text = ft.Text("Universal media downloader powered by yt-dlp", size=12, color=ft.colors.ON_SURFACE_VARIANT)
        
        header = ft.Row(
            controls=[
                logo_image,
                ft.Column(
                    controls=[title_text, subtitle_text],
                    spacing=2
                )
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        url_input = ft.TextField(
            label="Video URL",
            hint_text="Paste your video link here (e.g. YouTube, Twitter)...",
            prefix_icon=ft.icons.LINK,
            border_radius=8,
            expand=True
        )
        
        title_input = ft.TextField(
            label="Custom Output Title (Optional)",
            hint_text="Leave blank to use the default video name...",
            prefix_icon=ft.icons.TITLE,
            border_radius=8
        )
        
        folder_input = ft.TextField(
            label="Save Destination",
            value=page.client_storage.get("default_dir") or os.getcwd(),
            expand=True,
            border_radius=8
        )
        
        def on_folder_result(e: ft.FilePickerResultEvent):
            if e.path:
                folder_input.value = e.path
                page.update()
                
        folder_picker = ft.FilePicker(on_result=on_folder_result)
        page.overlay.append(folder_picker)
        folder_btn = ft.IconButton(
            icon=ft.icons.FOLDER_OPEN,
            on_click=lambda _: folder_picker.get_directory_path(),
            tooltip="Browse Save Folder"
        )
        
        # Initial Dropdown options
        res_dropdown = ft.Dropdown(
            label="Format / Resolution",
            options=[
                ft.dropdown.Option("Default (Best)"),
                ft.dropdown.Option("1080p"),
                ft.dropdown.Option("720p"),
                ft.dropdown.Option("480p"),
                ft.dropdown.Option("Audio Only (MP3)")
            ],
            value="720p",
            width=260,
            border_radius=8
        )
        
        tv_warning_text = ft.Text(
            "⚠️ Note: Resolutions above 1080p are not compatible with all TVs when TV Compatibility is enabled.",
            color=ft.colors.AMBER_400,
            size=11,
            weight=ft.FontWeight.BOLD,
            visible=False
        )

        def update_tv_warning():
            is_tv = page.client_storage.get("export_tv") is True
            selected = res_dropdown.value
            
            height = 0
            if selected:
                match = re.search(r'(\d+)', selected)
                if match:
                    height = int(match.group(1))
                    
            if is_tv and height > 1080:
                tv_warning_text.visible = True
            else:
                tv_warning_text.visible = False
                
        def on_res_change(e):
            update_tv_warning()
            page.update()
            
        res_dropdown.on_change = on_res_change
        
        playlist_switch = ft.Switch(
            label="Download Playlist (if detected)",
            value=False
        )
        
        cookies_switch = ft.Switch(
            label="Enable Cookie Authentication (Avoids bot blocks)",
            value=False
        )
        
        aria2_switch = ft.Switch(
            label="Enable Aria2 Extreme Speed Downloader Engine",
            value=False
        )
        
        cookie_file_input = ft.TextField(
            label="Cookies File (Netscape format)",
            hint_text="Path to cookies.txt...",
            expand=True,
            border_radius=8
        )
        
        def on_cookie_result(e: ft.FilePickerResultEvent):
            if e.files:
                cookie_file_input.value = e.files[0].path
                page.update()
                
        cookie_picker = ft.FilePicker(on_result=on_cookie_result)
        page.overlay.append(cookie_picker)
        cookie_btn = ft.IconButton(
            icon=ft.icons.FILE_OPEN,
            on_click=lambda _: cookie_picker.pick_files(allow_multiple=False),
            tooltip="Select cookies.txt"
        )
        
        cookie_paste = ft.TextField(
            label="Paste Netscape Cookies Text directly",
            multiline=True,
            min_lines=3,
            max_lines=5,
            border_radius=8
        )
        
        proxy_input = ft.TextField(
            label="Proxy Network Server (Optional)",
            hint_text="e.g., http://127.0.0.1:1080 or socks5://...",
            prefix_icon=ft.icons.LANGUAGE,
            border_radius=8
        )
        
        progress_bar = ft.ProgressBar(width=720, value=0, color=ft.colors.BLUE_ACCENT, bgcolor=ft.colors.SURFACE_VARIANT)
        progress_percent_text = ft.Text("0%", size=14, weight=ft.FontWeight.BOLD)
        
        log_view = ft.TextField(
            multiline=True,
            read_only=True,
            value="",
            text_style=ft.TextStyle(font_family="Consolas", size=12),
            expand=True,
            border_color=ft.colors.OUTLINE_VARIANT,
            min_lines=25,
            max_lines=30
        )
        
        def append_log(msg):
            log_view.value = (log_view.value or "") + msg + "\n"
            page.update()

        def copy_logs(e):
            page.set_clipboard(log_view.value)
            page.open(ft.SnackBar(ft.Text("Logs copied to clipboard!")))
            
        def clear_logs(e):
            log_view.value = ""
            log_view.update()
            
        # Queue List column
        queue_list_col = ft.Column(spacing=8)
        
        def update_queue_ui():
            queue_list_col.controls.clear()
            for i, item in enumerate(state["queue"]):
                status = item["status"]
                if status == "Queued":
                    status_control = ft.Icon(ft.icons.QUEUE, color=ft.colors.GREY_400)
                elif status == "Downloading":
                    status_control = ft.ProgressRing(width=16, height=16, stroke_width=2)
                elif status == "Success":
                    status_control = ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN_400)
                elif status == "Failed":
                    status_control = ft.Icon(ft.icons.ERROR, color=ft.colors.RED_400)
                elif status == "Paused":
                    status_control = ft.Icon(ft.icons.PAUSE_CIRCLE, color=ft.colors.AMBER_400)
                elif status == "Cancelled":
                    status_control = ft.Icon(ft.icons.CANCEL, color=ft.colors.GREY_500)
                    
                delete_btn = ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    icon_color=ft.colors.RED_400,
                    on_click=lambda e, idx=i: remove_from_queue(idx),
                    disabled=(status == "Downloading"),
                    tooltip="Remove from queue"
                )
                
                title_text = item["custom_title"] if item["custom_title"] else item["url"]
                if len(title_text) > 55:
                    title_text = title_text[:52] + "..."
                    
                item_row = ft.Container(
                    content=ft.Row(
                        controls=[
                            status_control,
                            ft.Column([
                                ft.Text(title_text, size=13, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Format: {item['resolution']} | Destination: {os.path.basename(item['output_dir'])}", size=10, color=ft.colors.ON_SURFACE_VARIANT)
                            ], expand=True, spacing=2),
                            delete_btn
                        ]
                    ),
                    padding=10,
                    border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
                    border_radius=8,
                    bgcolor=ft.colors.SURFACE_VARIANT if status == "Downloading" else ft.colors.TRANSPARENT
                )
                queue_list_col.controls.append(item_row)
            
            queue_card_title.value = f"Download Queue ({len(state['queue'])} items)"
            page.update()
            
        def remove_from_queue(index):
            if index < len(state["queue"]):
                state["queue"].pop(index)
                update_queue_ui()

        def process_next_queue_item():
            try:
                if not state["is_running"]:
                    return
                    
                # Find first item with "Queued" or "Paused" status
                queued_item = None
                queued_index = -1
                for idx, item in enumerate(state["queue"]):
                    if item["status"] in ["Queued", "Paused"]:
                        queued_item = item
                        queued_index = idx
                        break
                        
                if not queued_item:
                    state["is_running"] = False
                    pause_btn.disabled = True
                    cancel_btn.disabled = True
                    append_log("\n🎉 System: All queued downloads processed!")
                    page.open(ft.SnackBar(ft.Text("All queue downloads finished!")))
                    page.update()
                    update_queue_ui()
                    return
                    
                state["current_index"] = queued_index
                queued_item["status"] = "Downloading"
                update_queue_ui()
                
                def queue_progress(percent, speed, eta):
                    try:
                        progress_bar.value = percent
                        progress_percent_text.value = f"{int(percent * 100)}%"
                        speed_text.value = f"Speed: {speed}"
                        eta_text.value = f"ETA: {eta}"
                        page.update()
                    except:
                        pass
                    
                def queue_complete(success_status):
                    try:
                        if success_status == True:
                            queued_item["status"] = "Success"
                        elif success_status == "PAUSED":
                            queued_item["status"] = "Paused"
                            state["is_running"] = False
                        elif success_status == "CANCELLED":
                            queued_item["status"] = "Cancelled"
                        else:
                            queued_item["status"] = "Failed"
                            
                        update_queue_ui()
                    except Exception as e:
                        append_log(f"⚠️ Error updating queue UI: {str(e)}")
                        
                    # Run next item safely
                    try:
                        process_next_queue_item()
                    except Exception as e:
                        append_log(f"⚠️ Error launching next queue item: {str(e)}")
                    
                pause_btn.disabled = False
                cancel_btn.disabled = False
                page.update()
                
                downloader.start_download(
                    url=queued_item["url"],
                    format_str=queued_item["format_str"],
                    output_dir=queued_item["output_dir"],
                    custom_title=queued_item["custom_title"],
                    use_cookies=queued_item["use_cookies"],
                    cookie_file=queued_item["cookie_file"],
                    pasted_cookies=queued_item["pasted_cookies"],
                    proxy_url=queued_item["proxy_url"],
                    extract_audio=queued_item["extract_audio"],
                    download_playlist=queued_item["download_playlist"],
                    use_aria2=queued_item["use_aria2"],
                    custom_args=queued_item.get("custom_args", ""),
                    overwrite_defaults=queued_item.get("overwrite_defaults", False),
                    progress_callback=queue_progress,
                    log_callback=append_log,
                    completion_callback=queue_complete
                )
            except Exception as e:
                append_log(f"⚠️ Error processing next queue item: {str(e)}")
                state["is_running"] = False
                update_queue_ui()

        def add_to_queue(e):
            url = url_input.value.strip()
            if not url:
                append_log("❌ Error: Please enter a valid URL.")
                return
                
            resolution = res_dropdown.value
            export_tv = page.client_storage.get("export_tv") is True
            format_str = get_format_string(resolution, export_tv)
            output_dir = folder_input.value.strip()
            custom_title = title_input.value.strip()
            use_cookies = cookies_switch.value
            cookie_file = cookie_file_input.value.strip()
            pasted_cookies = cookie_paste.value.strip()
            proxy_url = proxy_input.value.strip()
            extract_audio = (resolution == "Audio Only (MP3)")
            download_playlist = playlist_switch.value
            use_aria2 = aria2_switch.value
            
            custom_args = custom_args_input.value.strip()
            overwrite_defaults = custom_args_overwrite_switch.value
            
            # Add to state queue list
            state["queue"].append({
                "url": url,
                "resolution": resolution,
                "format_str": format_str,
                "output_dir": output_dir,
                "custom_title": custom_title,
                "use_cookies": use_cookies,
                "cookie_file": cookie_file,
                "pasted_cookies": pasted_cookies,
                "proxy_url": proxy_url,
                "extract_audio": extract_audio,
                "download_playlist": download_playlist,
                "use_aria2": use_aria2,
                "custom_args": custom_args,
                "overwrite_defaults": overwrite_defaults,
                "status": "Queued"
            })
            
            # Clear input fields
            url_input.value = ""
            title_input.value = ""
            
            # Reset dropdown options to default
            res_dropdown.options = [
                ft.dropdown.Option("Default (Best)"),
                ft.dropdown.Option("1080p"),
                ft.dropdown.Option("720p"),
                ft.dropdown.Option("480p"),
                ft.dropdown.Option("Audio Only (MP3)")
            ]
            res_dropdown.value = "720p"
            
            update_queue_ui()
            page.open(ft.SnackBar(ft.Text("Added to download queue!")))

        def download_now(e):
            url = url_input.value.strip()
            if not url:
                if not any(item["status"] in ["Queued", "Paused"] for item in state["queue"]):
                    append_log("❌ Error: Please enter a URL or populate the queue.")
                    return
            else:
                # Add current to queue first
                add_to_queue(None)
                
            if not state["is_running"]:
                state["is_running"] = True
                process_next_queue_item()
                
        def pause_download(e):
            downloader.pause_download()
            pause_btn.disabled = True
            page.update()
            
        def cancel_download(e):
            downloader.cancel_download()
            cancel_btn.disabled = True
            pause_btn.disabled = True
            page.update()

        # --- INSPECT MEDIA FLOW ---
        def map_height_to_label(height):
            if height == 2160: return "2160p (4K)"
            if height == 1440: return "1440p (2K)"
            if height == 1080: return "1080p"
            if height == 720: return "720p"
            if height == 480: return "480p"
            if height == 360: return "360p"
            return f"{height}p"

        def on_inspect_complete(res):
            inspect_btn.disabled = False
            inspect_btn.text = "Inspect Link"
            
            if res["success"]:
                title_input.value = res["title"]
                
                # Rebuild dropdown options dynamically
                options = [ft.dropdown.Option("Default (Best)")]
                for h in res["resolutions"]:
                    options.append(ft.dropdown.Option(map_height_to_label(h)))
                options.append(ft.dropdown.Option("Audio Only (MP3)"))
                
                res_dropdown.options = options
                
                # Select the highest resolution available
                if res["resolutions"]:
                    res_dropdown.value = map_height_to_label(res["resolutions"][0])
                
                # Update TV warning visibility
                update_tv_warning()
                    
                append_log(f"✅ Metadata Inspection Success: '{res['title']}'")
                page.open(ft.SnackBar(ft.Text(f"Inspected: {res['title']}")))
            else:
                append_log(f"❌ Metadata Inspection Failed: {res['error']}")
                page.open(ft.SnackBar(ft.Text("Failed to inspect URL! Check logs.")))
            page.update()

        def inspect_url(e):
            url = url_input.value.strip()
            if not url:
                append_log("❌ Error: Please enter a URL to inspect.")
                return
                
            inspect_btn.disabled = True
            inspect_btn.text = "Inspecting..."
            page.update()
            
            downloader.inspect_media(
                url=url,
                use_cookies=cookies_switch.value,
                cookie_file=cookie_file_input.value.strip(),
                pasted_cookies=cookie_paste.value.strip(),
                proxy_url=proxy_input.value.strip(),
                callback=on_inspect_complete
            )

        def clear_queue(e):
            state["queue"].clear()
            state["is_running"] = False
            downloader.cancel_download()
            progress_bar.value = 0
            progress_percent_text.value = "0%"
            speed_text.value = "Speed: --"
            eta_text.value = "ETA: --"
            update_queue_ui()
            page.open(ft.SnackBar(ft.Text("Download queue cleared!")))

        def show_sensitive_warning_dialog(url):
            def on_confirm(e):
                page.close(dialog)
                trigger_download(url)
                
            def on_cancel(e):
                page.close(dialog)
                
            dialog = ft.AlertDialog(
                title=ft.Text("⚠️ Restricted Content Warning"),
                content=ft.Text(
                    "You are trying to download from a platform that frequently restricts or blocks "
                    "media unless you are authenticated (logged in).\n\n"
                    "If the download fails, please enable 'Use Netscape Cookies' and provide your cookies.\n\n"
                    "Do you want to attempt the download anyway?"
                ),
                actions=[
                    ft.TextButton("Download Anyway", on_click=on_confirm),
                    ft.TextButton("Cancel", on_click=on_cancel),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.open(dialog)

        # Standard downloader trigger wrapped for age warning dialog
        def trigger_download(url):
            add_to_queue(None)
            if not state["is_running"]:
                state["is_running"] = True
                process_next_queue_item()

        def start_download_click(e):
            url = url_input.value.strip()
            if not url:
                # If URL input is empty, just play the existing queue
                download_now(e)
                return
                
            is_sensitive_site = any(domain in url.lower() for domain in ["twitter.com", "x.com", "pornhub.com", "pornhubpremium.com", "onlyfans.com", "fansly.com"])
            if is_sensitive_site and not cookies_switch.value:
                show_sensitive_warning_dialog(url)
            else:
                trigger_download(url)

        # Action Buttons
        inspect_btn = ft.ElevatedButton(
            "Inspect Link",
            on_click=inspect_url,
            icon=ft.icons.FIND_IN_PAGE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
        )
        
        add_queue_btn = ft.ElevatedButton(
            "Add to Queue",
            on_click=add_to_queue,
            icon=ft.icons.ADD_TO_QUEUE,
            style=ft.ButtonStyle(
                padding=20,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )
        
        download_btn = ft.ElevatedButton(
            "Download Now",
            on_click=start_download_click,
            icon=ft.icons.PLAY_ARROW,
            bgcolor=ft.colors.BLUE_700,
            color=ft.colors.WHITE,
            style=ft.ButtonStyle(
                padding=20,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )
        
        pause_btn = ft.ElevatedButton(
            "Pause",
            on_click=pause_download,
            icon=ft.icons.PAUSE,
            disabled=True,
            style=ft.ButtonStyle(
                padding=20,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )
        
        cancel_btn = ft.ElevatedButton(
            "Cancel",
            on_click=cancel_download,
            icon=ft.icons.CANCEL,
            disabled=True,
            style=ft.ButtonStyle(
                padding=20,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )

        # UI Layout Panels
        # Row for URL and Inspect
        url_row = ft.Row([url_input, inspect_btn], spacing=10)

        # Section 1: Video Info
        video_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Source & Destination", size=16, weight=ft.FontWeight.BOLD),
                        url_row,
                        title_input,
                        ft.Row([folder_input, folder_btn]),
                    ],
                    spacing=12
                ),
                padding=16
            )
        )

        # Section 2: Options
        options_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Download Settings", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            controls=[res_dropdown, playlist_switch],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        tv_warning_text
                    ],
                    spacing=12
                ),
                padding=16
            )
        )

        # Section 3: Advanced Settings Tile
        advanced_accordion = ft.ExpansionTile(
            title=ft.Text("Advanced Settings (Authentication & Network)", size=15, weight=ft.FontWeight.BOLD),
            icon_color=ft.colors.BLUE_ACCENT,
            text_color=ft.colors.BLUE_ACCENT,
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            cookies_switch,
                            ft.Row([cookie_file_input, cookie_btn]),
                            cookie_paste,
                            proxy_input,
                            aria2_switch
                        ],
                        spacing=12
                    ),
                    padding=16,
                    border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
                    border_radius=8,
                    margin=ft.margin.only(top=10, bottom=10)
                )
            ]
        )

        # Section 4: Progress Panel
        progress_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Download Monitor", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row([download_btn, add_queue_btn, pause_btn, cancel_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                        ft.Divider(height=10, color="transparent"),
                        ft.Row(
                            controls=[
                                speed_text,
                                progress_percent_text,
                                eta_text
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        progress_bar
                    ],
                    spacing=10
                ),
                padding=16
            )
        )

        # Section 5: Download Queue Panel
        queue_card_title = ft.Text("Download Queue (0 items)", size=16, weight=ft.FontWeight.BOLD)
        start_queue_btn = ft.ElevatedButton("Start Queue", on_click=download_now, icon=ft.icons.PLAY_CIRCLE_FILL)
        clear_queue_btn = ft.ElevatedButton("Clear Queue", on_click=clear_queue, icon=ft.icons.CLEAR_ALL)
        
        queue_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                queue_card_title,
                                ft.Row([start_queue_btn, clear_queue_btn], spacing=8)
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        ft.Divider(height=5),
                        queue_list_col
                    ],
                    spacing=10
                ),
                padding=16
            )
        )

        # Assemble Tab 1 Content
        downloader_tab = ft.Column(
            controls=[
                video_card,
                options_card,
                advanced_accordion,
                progress_card,
                queue_card
            ],
            spacing=14
        )

        # Assemble Tab 2 Content
        logs_tab = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("System Output & Debug Logs", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            controls=[
                                ft.IconButton(
                                    icon=ft.icons.COPY,
                                    on_click=copy_logs,
                                    tooltip="Copy Logs to Clipboard"
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    on_click=clear_logs,
                                    tooltip="Clear Logs"
                                )
                            ]
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                log_view
            ],
            spacing=10,
            expand=True
        )

        def show_startup_guide():
            def close_dialog(e):
                page.close(dialog)
                
            def disable_guide(e):
                page.client_storage.set("show_bypass_guide", False)
                page.close(dialog)
                page.open(ft.SnackBar(ft.Text("Bypass guide disabled on startup.")))
                
            guide_text = (
                "If downloads from certain platforms fail due to ISP (Internet Service Provider) blocking "
                "or network filters, you can configure a custom secure DNS like NextDNS to easily bypass the blocks:\n\n"
                "⚙️ How to Setup Secure DNS on Windows:\n"
                "1. Open the Windows Settings app.\n"
                "2. Go to Network & internet.\n"
                "3. Click on Wi-Fi (or Ethernet depending on your connection).\n"
                "4. Click on Hardware properties (for Wi-Fi; ignore if on Ethernet).\n"
                "5. Click the Edit button next to DNS server assignment.\n"
                "6. Change the setting to Manual.\n"
                "7. Enable the IPv4 switch.\n"
                "8. Enter your NextDNS credentials:\n"
                "   • Preferred DNS: 45.90.28.0 (or your provider IP)\n"
                "   • Set DoH (DNS over HTTPS) to On (manual template)\n"
                "   • Template URL: https://dns.nextdns.io/{YourNextDNSID}\n"
                "   • Alternate DNS: 45.90.30.0\n"
                "   • Set DoH (DNS over HTTPS) to On (manual template)\n"
                "   • Template URL: https://dns.nextdns.io/{YourNextDNSID}\n"
                "9. Click Save to apply.\n\n"
                "Tip: You can also use Cloudflare's secure DNS (1.1.1.1 and 1.0.0.1) if you do not have a custom NextDNS profile."
            )
            
            dialog = ft.AlertDialog(
                title=ft.Text("🌐 Network & ISP Block Bypass Guide"),
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(guide_text, size=13, selectable=True)
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True
                    ),
                    width=600,
                    height=450
                ),
                actions=[
                    ft.TextButton("Don't Show Again", on_click=disable_guide),
                    ft.TextButton("Close", on_click=close_dialog),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.open(dialog)

        # --- SETTINGS TAB ---
        settings_folder_input = ft.TextField(
            label="Default Save Destination",
            value=page.client_storage.get("default_dir") or os.getcwd(),
            expand=True,
            border_radius=8
        )
        
        def on_settings_folder_result(e: ft.FilePickerResultEvent):
            if e.path:
                settings_folder_input.value = e.path
                page.client_storage.set("default_dir", e.path)
                folder_input.value = e.path
                page.update()
                
        settings_folder_picker = ft.FilePicker(on_result=on_settings_folder_result)
        page.overlay.append(settings_folder_picker)
        settings_folder_btn = ft.IconButton(
            icon=ft.icons.FOLDER_OPEN,
            on_click=lambda _: settings_folder_picker.get_directory_path(),
            tooltip="Browse Save Folder"
        )
        
        def save_default_dir(e):
            page.client_storage.set("default_dir", settings_folder_input.value.strip())
            folder_input.value = settings_folder_input.value.strip()
            page.open(ft.SnackBar(ft.Text("Default save destination saved!")))
            page.update()

        theme_dropdown = ft.Dropdown(
            label="Accent Theme Color",
            options=[
                ft.dropdown.Option("blue"),
                ft.dropdown.Option("purple"),
                ft.dropdown.Option("green"),
                ft.dropdown.Option("orange"),
                ft.dropdown.Option("red"),
                ft.dropdown.Option("teal"),
                ft.dropdown.Option("pink")
            ],
            value=initial_theme_color,
            width=200,
            border_radius=8
        )
        
        def on_theme_change(e):
            color = theme_dropdown.value
            theme_color_map = {
                "blue": ft.colors.BLUE_ACCENT,
                "purple": ft.colors.PURPLE_ACCENT,
                "green": ft.colors.GREEN_ACCENT,
                "orange": ft.colors.ORANGE_ACCENT,
                "red": ft.colors.RED_ACCENT,
                "teal": ft.colors.TEAL_ACCENT,
                "pink": ft.colors.PINK_ACCENT
            }
            page.theme = ft.Theme(color_scheme_seed=theme_color_map.get(color, ft.colors.BLUE_ACCENT))
            page.client_storage.set("theme_color", color)
            page.update()
            
        theme_dropdown.on_change = on_theme_change

        mode_switch = ft.Switch(
            label="Light Mode",
            value=(initial_mode == "light")
        )
        
        def on_mode_change(e):
            page.theme_mode = ft.ThemeMode.LIGHT if mode_switch.value else ft.ThemeMode.DARK
            page.client_storage.set("theme_mode", "light" if mode_switch.value else "dark")
            page.update()
            
        mode_switch.on_change = on_mode_change

        guide_switch = ft.Switch(
            label="Show Bypass Guide on program startup",
            value=(page.client_storage.get("show_bypass_guide") is not False)
        )
        
        def on_guide_pref_change(e):
            page.client_storage.set("show_bypass_guide", guide_switch.value)
            page.update()
            
        guide_switch.on_change = on_guide_pref_change

        # Custom arguments inputs
        custom_args_input = ft.TextField(
            label="Custom yt-dlp Command Line Arguments",
            value=page.client_storage.get("custom_args") or "",
            border_radius=8,
            hint_text="e.g., --limit-rate 1M --no-mtime --user-agent '...'"
        )
        
        def on_custom_args_change(e):
            page.client_storage.set("custom_args", custom_args_input.value.strip())
        custom_args_input.on_change = on_custom_args_change

        custom_args_overwrite_switch = ft.Switch(
            label="Overwrite default arguments (Instead of Appending)",
            value=page.client_storage.get("custom_args_overwrite") is True
        )
        
        def on_overwrite_change(e):
            page.client_storage.set("custom_args_overwrite", custom_args_overwrite_switch.value)
        custom_args_overwrite_switch.on_change = on_overwrite_change

        use_extension_cookies_switch = ft.Switch(
            label="Use Browser Extension Cookies (Automated)",
            value=page.client_storage.get("use_extension_cookies") is not False
        )
        
        def on_use_ext_cookies_change(e):
            page.client_storage.set("use_extension_cookies", use_extension_cookies_switch.value)
            page.update()
        use_extension_cookies_switch.on_change = on_use_ext_cookies_change

        export_tv_switch = ft.Switch(
            label="Export for TV Compatibility (H.264 / AAC)",
            value=page.client_storage.get("export_tv") is True
        )
        
        def on_export_tv_change(e):
            page.client_storage.set("export_tv", export_tv_switch.value)
            update_tv_warning()
            page.update()
        export_tv_switch.on_change = on_export_tv_change

        settings_tab = ft.Column(
            controls=[
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Download Directory Preferences", size=16, weight=ft.FontWeight.BOLD),
                            ft.Row([settings_folder_input, settings_folder_btn]),
                            ft.ElevatedButton("Save Default Folder", on_click=save_default_dir, icon=ft.icons.SAVE)
                        ], spacing=12),
                        padding=16
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Theme & Visuals", size=16, weight=ft.FontWeight.BOLD),
                            ft.Row([theme_dropdown, mode_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        ], spacing=12),
                        padding=16
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Advanced yt-dlp Configuration", size=16, weight=ft.FontWeight.BOLD),
                            custom_args_input,
                            custom_args_overwrite_switch,
                            use_extension_cookies_switch,
                            export_tv_switch
                        ], spacing=12),
                        padding=16
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("App Behavior", size=16, weight=ft.FontWeight.BOLD),
                            guide_switch
                        ], spacing=12),
                        padding=16
                    )
                )
            ],
            spacing=14
        )

        # Tabs Layout
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Downloader", icon=ft.icons.DOWNLOAD, content=downloader_tab),
                ft.Tab(text="Console Logs", icon=ft.icons.TERMINAL, content=logs_tab),
                ft.Tab(text="Settings", icon=ft.icons.SETTINGS, content=settings_tab),
            ],
            expand=True
        )

        # Overall Layout
        layout = ft.Column(
            controls=[
                header,
                ft.Divider(height=15, color=ft.colors.OUTLINE_VARIANT),
                tabs
            ],
            spacing=10,
            expand=True
        )

        page.add(layout)
        
        # Initial TV warning update
        update_tv_warning()
        
        # Check and show startup guide if not disabled
        if page.client_storage.get("show_bypass_guide") is not False:
            show_startup_guide()

    # assets_dir tells Flet to look in the 'assets' folder for images and icons
    ft.app(target=main, assets_dir="assets")
