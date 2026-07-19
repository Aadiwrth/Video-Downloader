import sys
import os

# Add current dir to path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui.flet_app import run_flet_app

def main():
    run_flet_app()

if __name__ == "__main__":
    main()
