"""Shared embedded PDF view, including the missing-registration fallback."""

from hashlib import sha256

import streamlit as st
from streamlit.errors import StreamlitAPIException


def show_pdf_preview(data, key_prefix, height=900):
    try:
        st.pdf(data, height=height, key=key_prefix + sha256(data).hexdigest())
    except StreamlitAPIException as error:
        if "streamlit-pdf.pdf_viewer" not in str(error) or "asset_dir" not in str(error):
            raise
        st.warning("The PDF viewer is not registered in this running server. Restart Streamlit "
                   "after installing its PDF component, then open the page again. "
                   "The generated PDF is available for download below.")
