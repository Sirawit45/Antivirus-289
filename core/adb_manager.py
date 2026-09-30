import os
import subprocess
import threading
import time
import re
from . import get_base_dir, get_app_dir
from .logger import logger

class AdbManager:
    def __init__(self, custom_adb_path=None):
        self.base_dir = get_base_dir()
        self.app_dir = get_app_dir()
        self.adb_path = self._resolve_adb_path(custom_adb_path)
        self.connected_device = None
        self.device_info = {}
        self.is_monitoring = False
        self._monitor_thread = None
        self.device_listeners = []
        self._lock = threading.Lock()
        self.simulator_mode = False

    def _resolve_adb_path(self, custom_path):
        if custom_path and os.path.exists(custom_path):
            return custom_path

        app_bin = os.path.join(self.app_dir, "bin", "adb", "adb.exe")
        if os.path.exists(app_bin):
            return app_bin

        base_bin = os.path.join(self.base_dir, "bin", "adb", "adb.exe")
        if os.path.exists(base_bin):
            return base_bin

        c_adb = r"C:\adb\adb.exe"
        if os.path.exists(c_adb):
            return c_adb

        import shutil
        path_adb = shutil.which("adb")
        if path_adb:
            return path_adb

        return app_bin

    def subscribe_device_change(self, callback):
        with self._lock:
            if callback not in self.device_listeners:
                self.device_listeners.append(callback)

    def unsubscribe_device_change(self, callback):
        with self._lock:
            if callback in self.device_listeners:
                self.device_listeners.remove(callback)

    def _notify_device_change(self):
        with self._lock:
            dev = dict(self.device_info) if self.connected_device else None
            for cb in list(self.device_listeners):
                try:
                    cb(dev)
                except Exception:
                    pass

    def run_cmd(self, args, timeout=8):
        """Run an ADB command with timeout and hidden console"""
        if self.simulator_mode:
            return self._run_simulator_cmd(args)

        if not os.path.exists(self.adb_path) and not self._is_system_adb():
            return "", f"ADB binary not found at {self.adb_path}", 1

        cmd = [self.adb_path] + args
        try:
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return stdout.strip(), stderr.strip(), proc.returncode
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            return "", "Command timed out", 1
        except Exception as e:
            return "", str(e), 1

    def _is_system_adb(self):
        import shutil
        return shutil.which("adb") is not None

    def start_server(self):
        out, err, code = self.run_cmd(["start-server"], timeout=6)
        return code == 0

    def kill_server(self):
        self.run_cmd(["kill-server"], timeout=4)

    def get_devices(self):
        """Returns list of dict: [{'serial': '...', 'state': 'device|unauthorized|offline'}]"""
        if self.simulator_mode:
            return [{"serial": "SIMULATOR-289-VIP", "state": "device"}]

        out, err, code = self.run_cmd(["devices"], timeout=4)
        devices = []
        if code == 0:
            lines = out.splitlines()
            for line in lines[1:]:
                parts = line.strip().split()
                if len(parts) >= 2:
                    devices.append({"serial": parts[0], "state": parts[1]})
        return devices

    def refresh_device_info(self, serial=None):
        """Fetch all details for connected device in 1 fast batch"""
        if self.simulator_mode:
            self.connected_device = "SIMULATOR-289-VIP"
            self.device_info = {
                "serial": "SIMULATOR-289-VIP",
                "state": "device",
                "brand": "Samsung",
                "model": "Galaxy S24 Ultra (Demo)",
                "android_version": "14",
                "sdk_version": "34",
                "build_id": "UP1A.231005.007.S928BXXU1AXB5",
                "security_patch": "2026-08-01",
                "battery": "92%",
                "battery_status": "Discharging",
                "cpu": "arm64-v8a",
                "root": "No",
                "user_apps_count": 16,
                "system_apps_count": 387,
                "disabled_apps_count": 2,
                "is_simulator": True
            }
            self._notify_device_change()
            return self.device_info

        devices = self.get_devices()
        ready_devices = [d for d in devices if d["state"] == "device"]

        if not ready_devices:
            self.connected_device = None
            self.device_info = {}
            self._notify_device_change()
            return None

        target = None
        if serial:
            target = next((d for d in ready_devices if d["serial"] == serial), None)
        if not target:
            target = ready_devices[0]

        dev_serial = target["serial"]
        self.connected_device = dev_serial

        # Fetch ALL getprop properties in 1 SINGLE call (Super fast!)
        props_out, _, _ = self.run_cmd(["-s", dev_serial, "shell", "getprop"], timeout=4)
        prop_map = {}
        for m in re.finditer(r"\[(.*?)\]:\s*\[(.*?)\]", props_out):
            prop_map[m.group(1)] = m.group(2)

        brand = prop_map.get("ro.product.brand") or prop_map.get("ro.product.manufacturer") or "Android"
        model = prop_map.get("ro.product.model") or "Device"
        android_ver = prop_map.get("ro.build.version.release") or "Unknown"
        sdk_ver = prop_map.get("ro.build.version.sdk") or "Unknown"
        build_id = prop_map.get("ro.build.display.id") or prop_map.get("ro.build.id") or "Unknown"
        security_patch = prop_map.get("ro.build.version.security_patch") or "Unknown"
        cpu = prop_map.get("ro.product.cpu.abi") or "arm64"

        # Battery in 1 quick call
        battery = "100%"
        battery_status = "Good"
        bat_out, _, _ = self.run_cmd(["-s", dev_serial, "shell", "dumpsys", "battery"], timeout=3)
        m_level = re.search(r"level:\s*(\d+)", bat_out)
        if m_level:
            battery = f"{m_level.group(1)}%"

        info = {
            "serial": dev_serial,
            "state": "device",
            "brand": brand.capitalize(),
            "model": model,
            "android_version": android_ver,
            "sdk_version": sdk_ver,
            "build_id": build_id,
            "security_patch": security_patch,
            "battery": battery,
            "battery_status": battery_status,
            "cpu": cpu,
            "root": "No",
            "user_apps_count": 0,
            "system_apps_count": 0,
            "disabled_apps_count": 0,
            "is_simulator": False
        }

        self.device_info = info
        self._notify_device_change()

        logger.success(f"Device connected: {dev_serial} ({info['brand']} {info['model']})", "อุปกรณ์เชื่อมต่อสำเร็จ")
        return info

    def start_monitoring(self, poll_interval=3.0):
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(poll_interval,), daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        self.is_monitoring = False

    def _monitor_loop(self, interval):
        self.start_server()
        last_serial = None
        while self.is_monitoring:
            try:
                devices = self.get_devices()
                ready = [d for d in devices if d["state"] == "device"]
                unauth = [d for d in devices if d["state"] == "unauthorized"]

                if unauth and not ready:
                    logger.warning("Device unauthorized! Please check phone screen.", "กรุณากด 'อนุญาต (Allow)' ที่หน้าจอมือถือ")

                if ready:
                    current_serial = ready[0]["serial"]
                    if current_serial != last_serial or not self.device_info:
                        last_serial = current_serial
                        self.refresh_device_info(current_serial)
                else:
                    if last_serial is not None:
                        logger.warning("Device disconnected", "อุปกรณ์ถูกถอดการเชื่อมต่อ")
                        last_serial = None
                        self.connected_device = None
                        self.device_info = {}
                        self._notify_device_change()
            except Exception:
                pass
            time.sleep(interval)

    def set_simulator_mode(self, enabled=True):
        self.simulator_mode = enabled
        if enabled:
            logger.info("Simulator Mode Activated", "เปิดโหมดจำลองอุปกรณ์สำหรับทดสอบ")
        else:
            logger.info("Simulator Mode Deactivated", "ปิดโหมดจำลองอุปกรณ์")
        self.refresh_device_info()

    def _run_simulator_cmd(self, args):
        cmd_str = " ".join(args)
        if "devices" in cmd_str:
            return "List of devices attached\nSIMULATOR-289-VIP\tdevice", "", 0
        elif "getprop" in cmd_str:
            return "[ro.product.brand]: [Samsung]\n[ro.product.model]: [SM-S928B Galaxy S24 Ultra]\n[ro.build.version.release]: [14]\n[ro.build.version.sdk]: [34]\n[ro.build.display.id]: [UP1A.231005.007.S928BXXU1AXB5]\n[ro.build.version.security_patch]: [2026-08-01]\n[ro.product.cpu.abi]: [arm64-v8a]", "", 0
        elif "pm list packages -3" in cmd_str:
            sim_pkgs = [
                "package:com.revenuedepartment.app",
                "package:com.zenthaq4729.meeting_agenda_builder_8301",
                "package:com.space.whizclear.qub",
                "package:borrorhealthcare.store",
                "package:com.nanai.cleanfly",
                "package:jp.naver.line.android",
                "package:com.facebook.katana",
                "package:com.ss.android.ugc.trill",
                "package:com.kasikorn.retail.mbanking.wap",
                "package:com.scb.phone",
                "package:ktbcs.netbank",
                "package:com.tmn_android",
                "package:com.shopee.th",
                "package:com.lazada.android",
                "package:com.grabtaxi.passenger",
                "package:com.duokan.phone.remotecontroller"
            ]
            return "\n".join(sim_pkgs), "", 0
        elif "pm list packages -s" in cmd_str:
            return "package:com.android.settings\npackage:com.android.systemui\npackage:com.google.android.gms", "", 0
        elif "pm list packages -d" in cmd_str:
            return "package:com.sec.android.app.samsungapps\npackage:com.google.android.videos", "", 0
        elif "pm list packages -i" in cmd_str:
            return "package:com.revenuedepartment.app installer=null\npackage:jp.naver.line.android installer=com.android.vending", "", 0
        elif "uninstall" in cmd_str or "pm uninstall" in cmd_str:
            return "Success", "", 0
        elif "settings put global" in cmd_str:
            return "", "", 0
        return "", "", 0

# Global ADB manager singleton
adb_manager = AdbManager()
