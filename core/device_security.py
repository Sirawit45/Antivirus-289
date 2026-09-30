import os
import sys
import subprocess
import threading
from . import get_base_dir, get_app_dir
from .adb_manager import adb_manager
from .logger import logger

class DeviceSecurity:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.app_dir = get_app_dir()
        if os.path.exists(os.path.join(self.app_dir, "assets", "drivers")):
            self.drivers_dir = os.path.join(self.app_dir, "assets", "drivers")
        else:
            self.drivers_dir = os.path.join(self.base_dir, "assets", "drivers")

    def disable_adb(self):
        logger.info("Attempting to disable ADB...", "กำลังพยายามปิด USB Debugging...")
        dev_serial = adb_manager.connected_device or ("SIMULATOR-289-VIP" if adb_manager.simulator_mode else None)
        if not dev_serial:
            logger.warning("No device connected", "ไม่พบอุปกรณ์")
            return False, "No device connected"

        out, err, code = adb_manager.run_cmd(["-s", dev_serial, "shell", "settings", "put", "global", "adb_enabled", "0"])
        if code == 0:
            logger.success("ADB disabled successfully", "ปิดดีบัคสำเร็จ")
            return True, "ADB disabled successfully"
        else:
            logger.warning("Not supported. Please set it manually.", "ไม่สามารถปิดดีบัคอัตโนมัติได้ กรุณาปิดที่การตั้งค่าในมือถือ")
            return False, "Not supported on this Android OS version"

    def disable_developer_settings(self):
        logger.info("Attempting to disable developer settings...", "พยายามปิดเมนูตัวเลือกสำหรับนักพัฒนา...")
        dev_serial = adb_manager.connected_device or ("SIMULATOR-289-VIP" if adb_manager.simulator_mode else None)
        if not dev_serial:
            logger.warning("No device connected", "ไม่พบอุปกรณ์")
            return False, "No device connected"

        out, err, code = adb_manager.run_cmd(["-s", dev_serial, "shell", "settings", "put", "global", "development_settings_enabled", "0"])
        if code == 0:
            logger.success("Developer settings disabled successfully", "ปิดเมนูนักพัฒนาให้แล้ว")
            return True, "Developer settings disabled successfully"
        else:
            logger.warning("Not supported. Please set it manually.", "ไม่สามารถปิดเมนูนักพัฒนาได้ กรุณาปิดเอง")
            return False, "Not supported on this Android OS version"

    def reboot(self, mode="normal"):
        dev_serial = adb_manager.connected_device or ("SIMULATOR-289-VIP" if adb_manager.simulator_mode else None)
        if not dev_serial:
            return False, "No device connected"

        args = ["-s", dev_serial, "reboot"]
        if mode == "recovery":
            args.append("recovery")
        elif mode == "bootloader":
            args.append("bootloader")

        logger.info(f"Rebooting device ({mode})...", f"กำลังรีสตาร์ทเครื่อง ({mode})...")
        out, err, code = adb_manager.run_cmd(args)
        if code == 0:
            logger.success("Reboot signal sent", "ส่งคำสั่งรีสตาร์ทเรียบร้อย")
            return True, "Success"
        return False, err or out

    def install_samsung_driver(self):
        exe_path = os.path.join(self.drivers_dir, "SAMSUNG_USB_Driver_for_Mobile_Phones_v1.9.0.0.exe")
        if not os.path.exists(exe_path):
            exe_path = r"C:\AntivirusAPks\SAMSUNG_USB_Driver_for_Mobile_Phones_v1.9.0.0.exe"

        if os.path.exists(exe_path):
            logger.info("Launching Samsung Mobile USB Driver Installer...", "กำลังเปิดตัวติดตั้ง Samsung Driver...")
            try:
                subprocess.Popen([exe_path], shell=True)
                return True, "Launched installer"
            except Exception as e:
                return False, str(e)
        return False, "Driver executable not found"

    def install_universal_adb_driver(self):
        msi_path = os.path.join(self.drivers_dir, "UniversalAdbDriverSetup.msi")
        if not os.path.exists(msi_path):
            msi_path = r"C:\AntivirusAPks\UniversalAdbDriverSetup.msi"

        if os.path.exists(msi_path):
            logger.info("Launching Universal ADB Driver Installer...", "กำลังเปิดตัวติดตั้ง Universal ADB Driver...")
            try:
                subprocess.Popen(["msiexec", "/i", msi_path], shell=True)
                return True, "Launched installer"
            except Exception as e:
                return False, str(e)
        return False, "MSI installer not found"

# Global device security singleton
device_security = DeviceSecurity()
