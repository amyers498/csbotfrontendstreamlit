"""
CryptoandStockBot2026 - Streamlit Application Entrypoint.
Delegates directly to streamlit_app.py for seamless compatibility across both
'streamlit run app.py' and 'streamlit run streamlit_app.py'.
"""

import os
import runpy

app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streamlit_app.py")
runpy.run_path(app_path, run_name="__main__")
