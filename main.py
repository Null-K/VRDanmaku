import sys
import os
import logging
import warnings

logging.getLogger('pywebview').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

from ui.control_panel import main

if __name__ == "__main__":
    main()
