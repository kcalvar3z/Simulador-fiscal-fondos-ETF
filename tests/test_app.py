from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from app import AVISO_LEGAL, a_decimal, formato_euros
from simulador.lotes import TipoProducto

D = Decimal
CUOTA = "Cuota de IRPF en 2026"
RETENCION = "Retención al vender (pago a cuenta)"
EFECTO_RENTA = "Efecto en la Renta (cuota − retención)"
LATENTE = "Impuesto latente (diferido)"


@pytest.mark.parametrize(
    ("importe", "texto"),
    [
        (D("1980"), "1.980,00 €"),
        (D("-190"), "-190,00 €"),
        (D("1234567.891"), "1.234.567,89 €"),
        (D("0.005"), "0,01 €"),
        (D("-0.001"), "0,00 €"),
    ],
)
def test_formato_euros(importe, texto):
    assert formato_euros(importe) == texto


def test_a_decimal_no_arrastra_el_error_del_float():
    assert a_decimal(0.1) == D("0.1")


def ejecutar_app() -> AppTest:
    app = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not app.exception
    return app


def tabla_resultados(app: AppTest):
    """La tabla comparativa es la que tiene la cuota como fila (la primera es el editor de compras)."""
    return next(tabla.value for tabla in app.dataframe if CUOTA in tabla.value.index)


def test_app_muestra_el_caso_b_por_defecto():
    app = ejecutar_app()
    tabla = tabla_resultados(app)

    # Con un fondo solo se muestran sus dos escenarios.
    assert list(tabla.columns) == ["Reembolso del fondo", "Traspaso a otro fondo"]
    reembolso = tabla["Reembolso del fondo"]
    assert (reembolso[CUOTA], reembolso[RETENCION], reembolso[EFECTO_RENTA]) == ("1.980,00 €", "1.900,00 €", "80,00 €")
    assert tabla["Traspaso a otro fondo"][LATENTE] == "1.980,00 €"
    assert any(AVISO_LEGAL in aviso.value for aviso in app.info)


def test_app_con_etf_marca_el_traspaso_como_no_disponible():
    app = ejecutar_app()
    app.radio(key="producto").set_value(TipoProducto.ETF).run()
    assert not app.exception
    tabla = tabla_resultados(app)

    assert list(tabla.columns) == ["Venta del ETF", "Traspaso a otro fondo"]
    etf = tabla["Venta del ETF"]
    assert (etf[CUOTA], etf[RETENCION]) == ("1.980,00 €", "0,00 €")
    assert (tabla["Traspaso a otro fondo"] == "No disponible").all()
