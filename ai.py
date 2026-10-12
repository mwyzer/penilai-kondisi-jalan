"""Pemilihan penyedia AI (DeepSeek atau Claude) dan pembacaan pengaturan."""
import os

import streamlit as st

from analisis import HasilAnalisis, analisis_claude
from analisis_deepseek import analisis_deepseek


def pengaturan(nama: str, default=None):
    """Baca dari .streamlit/secrets.toml, lalu dari environment variable."""
    try:
        if nama in st.secrets:
            return st.secrets[nama]
    except Exception:  # tidak ada secrets.toml
        pass
    return os.environ.get(nama, default)


def pakai_claude() -> bool:
    return pengaturan("AI_PROVIDER", "deepseek") == "claude"


def nama_penyedia() -> str:
    return "Claude" if pakai_claude() else "DeepSeek"


def analisis_ai(data: bytes, konteks: str) -> HasilAnalisis:
    if pakai_claude():
        return analisis_claude(data, konteks, pengaturan("ANTHROPIC_API_KEY"))
    return analisis_deepseek(data, konteks, pengaturan("DEEPSEEK_API_KEY"))
