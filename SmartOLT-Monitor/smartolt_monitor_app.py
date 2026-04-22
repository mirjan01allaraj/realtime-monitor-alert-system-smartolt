# smartolt_monitor_app.py
# GUI controller for SmartOLT Monitor backend (monitor_server.py)
# - CustomTkinter dark glass-like GUI
# - Start Flask backend in background
# - Telegram ON/OFF live
# - System + Notification logs
# - TWO tray icons (Online & Offline, neon numbers only, dynamic size)
# - Shared tray menu (Show / Quit)
# - X → Hide to tray (app vazhdon të punojë)

import threading
import os
import webbrowser

import requests
import customtkinter as ctk

import monitor_server as backend  # same folder

# Tray icons
import pystray
from PIL import Image, ImageDraw, ImageFont

# ---------------- CONFIG ----------------
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 5005
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

LOGS_POLL_INTERVAL = 1.0  # seconds

# ---------------- SERVER THREAD ----------------
server_thread = None
server_running = False


def run_backend_server():
    global server_running
    server_running = True
    try:
        backend.log_system("GUI: Starting Flask backend")
        backend.app.run(
            host=BACKEND_HOST,
            port=BACKEND_PORT,
            debug=False,
            use_reloader=False,
        )
    except Exception as e:
        backend.log_system(f"GUI: Backend server crashed: {e}")
    finally:
        server_running = False
        backend.log_system("GUI: Backend server thread exited")


# =====================================================================
#                      GUI APPLICATION
# =====================================================================

class SmartOLTMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window basics
        self.title("SmartOLT Monitor – Desktop Controller")
        self.geometry("900x600")
        self.minsize(800, 500)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Tray icon state
        self.tray_icon_online = None
        self.tray_icon_offline = None
        self.tray_font = None
        # real default currently 60s (comment used to say 5m)
        self.tray_interval_seconds = 60
        self.tray_updater_started = False

        # X → hide to tray
        self.protocol("WM_DELETE_WINDOW", self.on_close_to_tray)

        # === GUI Layout ===
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # =================================================================
        # HEADER
        # =================================================================
        self.header_frame = ctk.CTkFrame(self, corner_radius=15)
        self.header_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")
        self.header_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="SmartOLT Multi-Region Monitor",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#27bcd8",
        )
        self.title_label.grid(row=0, column=0, padx=15, pady=(10, 0), sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="Created by: Mallaraj",
            font=ctk.CTkFont(size=13),
            text_color="white",
        )
        self.subtitle_label.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")

        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text="Server: STOPPED",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#ff5555",
        )
        self.status_label.grid(row=0, column=1, padx=15, pady=(10, 0), sticky="e")

        # Telegram checkbox
        self.telegram_var = ctk.BooleanVar(value=backend.TELEGRAM_ENABLED)
        self.telegram_checkbox = ctk.CTkCheckBox(
            self.header_frame,
            text="Send Telegram alerts",
            variable=self.telegram_var,
            command=self.on_toggle_telegram,
        )
        self.telegram_checkbox.grid(row=1, column=1, padx=15, pady=(0, 10), sticky="e")

        # Tray interval
        self.tray_label = ctk.CTkLabel(
            self.header_frame,
            text="Tray icon Time:",
            font=ctk.CTkFont(size=13),
        )
        self.tray_label.grid(row=0, column=2, padx=10, pady=(10, 0), sticky="e")

        self.tray_interval_box = ctk.CTkComboBox(
            self.header_frame,
            values=["1s", "30s", "1m", "3m", "5m", "7m", "10m"],
            command=self.on_tray_interval_change,
            width=100,
        )
        self.tray_interval_box.set("5m")
        self.tray_interval_box.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="e")

        # =================================================================
        # BUTTON BAR
        # =================================================================
        self.button_frame = ctk.CTkFrame(self, corner_radius=10)
        self.button_frame.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.start_btn = ctk.CTkButton(
            self.button_frame,
            text="Start Server",
            fg_color="#4CAF50",
            hover_color="#45a049",
            command=self.on_start_server,
        )
        self.start_btn.grid(row=0, column=0, padx=5, pady=8, sticky="ew")

        self.stop_btn = ctk.CTkButton(
            self.button_frame,
            text="Stop Server",
            fg_color="#f44336",
            hover_color="#e53935",
            command=self.on_stop_server,
        )
        self.stop_btn.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        self.reload_btn = ctk.CTkButton(
            self.button_frame,
            text="Reload / Ping",
            fg_color="#FFC107",
            hover_color="#ffb300",
            text_color="black",
            command=self.on_reload_server,
        )
        self.reload_btn.grid(row=0, column=2, padx=5, pady=8, sticky="ew")

        self.open_logs_btn = ctk.CTkButton(
            self.button_frame,
            text="Open Logs Folder",
            fg_color="#2196F3",
            hover_color="#1e88e5",
            command=self.on_open_logs,
        )
        self.open_logs_btn.grid(row=0, column=3, padx=5, pady=8, sticky="ew")

        self.test_dashboard_btn = ctk.CTkButton(
            self.button_frame,
            text="Open Test Dashboard",
            fg_color="#9C27B0",
            hover_color="#8e24aa",
            command=self.on_open_test_dashboard,
        )
        self.test_dashboard_btn.grid(row=0, column=4, padx=5, pady=8, sticky="ew")

        # =================================================================
        # LOG PANELS
        # =================================================================
        self.log_frame = ctk.CTkFrame(self, corner_radius=12)
        self.log_frame.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="nsew")
        self.log_frame.grid_columnconfigure((0, 1), weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        self.sys_title = ctk.CTkLabel(
            self.log_frame,
            text="System Log",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#2196F3",
        )
        self.sys_title.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.notif_title = ctk.CTkLabel(
            self.log_frame,
            text="Notification Log",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#2196F3",
        )
        self.notif_title.grid(row=0, column=1, padx=10, pady=(10, 0), sticky="w")

        self.system_log_text = ctk.CTkTextbox(self.log_frame, corner_radius=10)
        self.system_log_text.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        self.notif_log_text = ctk.CTkTextbox(self.log_frame, corner_radius=10)
        self.notif_log_text.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        self.footer_label = ctk.CTkLabel(
            self,
            text="Ready.",
            font=ctk.CTkFont(size=12),
            text_color="#bbbbbb",
        )
        self.footer_label.grid(row=3, column=0, padx=15, pady=(0, 10), sticky="w")

        # ---- Create TWO tray icons (Online & Offline)
        self.create_tray_icons()

        # Poll logs
        self.after(500, self.poll_logs_loop)

        # Start tray-updater
        self.after(2000, self.start_tray_updates)

    # =================================================================
    #                      TRAY ICONS (DUAL)
    # =================================================================

    def on_tray_interval_change(self, value: str):
        mapping = {
            "1s": 1,
            "30s": 30,
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "7m": 420,
            "10m": 600,
        }
        self.tray_interval_seconds = mapping.get(value, 60)
        self.footer_label.configure(text=f"Tray icon interval set to {value}")

    def create_tray_icons(self):
        # font për numrat (mbetet njësoj, ndryshojmë vetëm canvas size)
        try:
            self.tray_font = ImageFont.truetype("arial.ttf", 28)
        except Exception:
            self.tray_font = ImageFont.load_default()

        # fillimisht 0/0
        img_online = self._create_tray_image_online(0)
        img_offline = self._create_tray_image_offline(0)

        # shared menu për të dy ikonat
        menu = pystray.Menu(
            pystray.MenuItem("Show SmartOLT Monitor", self._tray_show_app),
            pystray.MenuItem("Quit", self._tray_quit_app),
        )

        # ONLINE icon
        self.tray_icon_online = pystray.Icon(
            "SmartOLT_Online",
            img_online,
            "Online: 0",
            menu,
        )

        # OFFLINE icon
        self.tray_icon_offline = pystray.Icon(
            "SmartOLT_Offline",
            img_offline,
            "Offline: 0",
            menu,
        )

        t1 = threading.Thread(target=self.tray_icon_online.run, daemon=True)
        t2 = threading.Thread(target=self.tray_icon_offline.run, daemon=True)
        t1.start()
        t2.start()

    # ---------- dynamic size helpers ----------

    def _get_icon_size_for_value(self, value: int) -> int:
        """
        1–99   → 32px
        100–999 → 40px
        1000+   → 48px
        """
        try:
            n = abs(int(value))
        except Exception:
            n = 0

        if n < 100:
            return 32
        elif n < 1000:
            return 40
        else:
            return 48

    def _create_empty_icon(self, size: int):
        """
        Krijon canvas transparent (size x size).
        """
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        return img, draw

    def _draw_neon_number_no_bg(self, draw, size: int, text: str, color):
        """
        Numër neon në qendër, pa background.
        Përdor textbbox për të marrë gjerësinë/lartësinë → centering.
        """
        try:
            bbox = draw.textbbox((0, 0), text, font=self.tray_font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except Exception:
            w, h = 16, 16

        x = (size - w) // 2
        y = (size - h) // 2

        glow = (color[0], color[1], color[2], 150)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                draw.text((x + dx, y + dy), text, font=self.tray_font, fill=glow)

        draw.text((x, y), text, font=self.tray_font, fill=color)

    def _create_tray_image_online(self, online: int):
        size = self._get_icon_size_for_value(online)
        img, draw = self._create_empty_icon(size)
        neon_green = (0, 255, 80, 255)
        self._draw_neon_number_no_bg(draw, size, str(online), neon_green)
        return img

    def _create_tray_image_offline(self, total_offline: int):
        size = self._get_icon_size_for_value(total_offline)
        img, draw = self._create_empty_icon(size)
        neon_red = (255, 40, 120, 255)
        self._draw_neon_number_no_bg(draw, size, str(total_offline), neon_red)
        return img

    def start_tray_updates(self):
        if not self.tray_updater_started:
            self.tray_updater_started = True
            self.update_tray_icons()

    def update_tray_icons(self):
        if not (self.tray_icon_online and self.tray_icon_offline):
            self.after(self.tray_interval_seconds * 1000, self.update_tray_icons)
            return

        online = 0
        total = 0
        try:
            r = requests.get(f"{BACKEND_URL}/status", timeout=1.5)
            if r.status_code == 200:
                st = r.json()
                online = int(st.get("online", 0))
                total = int(st.get("total", 0))
        except Exception:
            pass

        try:
            img_on = self._create_tray_image_online(online)
            self.tray_icon_online.icon = img_on
            self.tray_icon_online.title = f"Online: {online}"

            img_off = self._create_tray_image_offline(total)
            self.tray_icon_offline.icon = img_off
            self.tray_icon_offline.title = f"Offline: {total}"
        except Exception:
            pass

        self.after(self.tray_interval_seconds * 1000, self.update_tray_icons)

    # Tray callbacks (shared)
    def _tray_show_app(self, icon, item):
        self.after(0, self.deiconify)

    def _tray_quit_app(self, icon, item):
        def _quit():
            try:
                if self.tray_icon_online:
                    self.tray_icon_online.stop()
            except Exception:
                pass
            try:
                if self.tray_icon_offline:
                    self.tray_icon_offline.stop()
            except Exception:
                pass
            self.destroy()
        self.after(0, _quit)

    def on_close_to_tray(self):
        self.withdraw()
        self.footer_label.configure(
            text="App hidden to tray. Use tray icons → Show / Quit."
        )

    # =================================================================
    #                           BUTTONS
    # =================================================================

    def on_start_server(self):
        global server_thread, server_running

        if server_thread and server_running:
            self.footer_label.configure(text="Server already running.")
            return

        server_thread = threading.Thread(target=run_backend_server, daemon=True)
        server_thread.start()
        self.footer_label.configure(text="Starting backend server...")
        self.status_label.configure(text="Server: STARTING...", text_color="#ffcc00")

        self.after(2000, self._update_running_status)

    def _update_running_status(self):
        if server_running:
            self.status_label.configure(text="Server: RUNNING", text_color="#00e676")
            self.footer_label.configure(text=f"Backend running at {BACKEND_URL}")
        else:
            self.status_label.configure(text="Server: STOPPED", text_color="#ff5555")

    def on_stop_server(self):
        self.footer_label.configure(
            text="Stop i plotë bëhet duke dalë nga tray → Quit."
        )

    def on_reload_server(self):
        try:
            r = requests.get(f"{BACKEND_URL}/logs", timeout=2)
            if r.status_code == 200:
                self.footer_label.configure(text="Backend reachable.")
            else:
                self.footer_label.configure(text=f"Backend responded {r.status_code}.")
        except Exception as e:
            self.footer_label.configure(text=f"Backend unreachable: {e}")

    def on_open_logs(self):
        logs_dir = backend.LOGS_DIR
        try:
            os.startfile(logs_dir)
            self.footer_label.configure(text="Opened Logs folder.")
        except Exception as e:
            self.footer_label.configure(text=f"Cannot open Logs: {e}")

    def on_open_test_dashboard(self):
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_dashboard.html")
        if os.path.isfile(html_path):
            webbrowser.open_new_tab(f"file:///{html_path}")
        else:
            webbrowser.open_new_tab(BACKEND_URL)
        self.footer_label.configure(text="Opened Test Dashboard / Backend URL.")

    def on_toggle_telegram(self):
        enabled = self.telegram_var.get()
        backend.TELEGRAM_ENABLED = enabled
        backend.log_system(f"GUI: TELEGRAM_ENABLED set to {enabled}")
        self.footer_label.configure(
            text=f"Telegram alerts {'ENABLED' if enabled else 'DISABLED'}."
        )

    # =================================================================
    #                           LOG POLLING
    # =================================================================

    def poll_logs_loop(self):
        try:
            r = requests.get(f"{BACKEND_URL}/logs", timeout=1.5)
            if r.status_code == 200:
                data = r.json()
                sys_lines = data.get("system", [])
                notif_lines = data.get("notifications", [])

                self.system_log_text.configure(state="normal")
                self.system_log_text.delete("1.0", "end")
                self.system_log_text.insert("end", "\n\n".join(sys_lines))
                self.system_log_text.configure(state="disabled")

                self.notif_log_text.configure(state="normal")
                self.notif_log_text.delete("1.0", "end")
                self.notif_log_text.insert("end", "\n\n".join(notif_lines))
                self.notif_log_text.configure(state="disabled")

                self.system_log_text.see("end")
                self.notif_log_text.see("end")
        except Exception:
            pass

        self.after(int(LOGS_POLL_INTERVAL * 1000), self.poll_logs_loop)


# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    app = SmartOLTMonitorApp()
    app.mainloop()
