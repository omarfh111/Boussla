"""Presentation helpers; calculations and permissions stay in the service."""

from decimal import Decimal

from boussla.contracts import BousslaError, ErrorCode
import streamlit as st


def amount(millimes: int | None) -> str:
    if millimes is None:
        return "Non disponible"
    return f"{Decimal(millimes) / Decimal(1000):,.3f} TND".replace(",", " ")


def service_action(action, on_success=None):
    """Run a scoped service action and refresh after a stale case version."""
    try:
        result = action()
    except BousslaError as exc:
        if exc.code is ErrorCode.STALE_REVISION:
            st.warning("Le dossier a changé. Rechargez-le et vérifiez la nouvelle version avant de réessayer.")
        else:
            st.error(f"{exc.code.value} : {exc.message}")
        return None
    if on_success is not None:
        on_success(result)
    st.rerun()
