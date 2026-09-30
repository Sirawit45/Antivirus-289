import os
import sys

def get_base_dir():
    """Returns directory where static assets (UI, bundled data) are located."""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_app_dir():
    """Returns directory where user data and persistent files are saved."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

__version__ = "4.0.0"

