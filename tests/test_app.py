from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import (
    AVISO_LEGAL,
    TRASPASAR,
    VENDER,
    a_decimal,
    calcular_planes,
    formato_euros,
    leer_plan,
    mensaje_clave,
    tabla_comparativa,
    tabla_por_producto,
)
from simulador.escenarios import OtrasRentasAhorro

D = Decimal
CUOTA = "Cuota de IRPF en 2026"
RETENCION = "Retención al vender (pago a cuenta)"
EFECTO_RENTA = "Efecto en la Renta (cuota − retención)"
LATENTE = "Impuesto latente (diferido)"
FONDO = "Fondo de inversión"


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


# App completa con los datos de ejemplo (caso B)


def test_app_muestra_el_caso_b_por_defecto():
    app = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not app.exception
    tabla = next(t.value for t in app.dataframe if CUOTA in t.value.index)

    assert list(tabla.columns) == ["Reembolso del fondo", "Traspaso a otro fondo"]
    reembolso = tabla["Reembolso del fondo"]
    assert (reembolso[CUOTA], reembolso[RETENCION], reembolso[EFECTO_RENTA]) == ("1.980,00 €", "1.900,00 €", "80,00 €")
    assert tabla["Traspaso a otro fondo"][LATENTE] == "1.980,00 €"
    assert any(AVISO_LEGAL in aviso.value for aviso in app.info)


# Lectura de las tablas y planes mostrados


def compras(*filas) -> pd.DataFrame:
    """Filas: (producto, participaciones, precio). Todas compradas el 15-1-2023 sin comisión."""
    return pd.DataFrame(
        [(producto, date(2023, 1, 15), float(n), float(precio), 0.0) for producto, n, precio in filas],
        columns=["producto", "fecha", "participaciones", "precio_unitario", "comision"],
    )


def ventas(*filas) -> pd.DataFrame:
    """Filas: (producto, tipo, operación, precio). Se venden todas las participaciones el 16-10-2026."""
    return pd.DataFrame(
        [(producto, tipo, operacion, date(2026, 10, 16), None, float(precio), 0.0) for producto, tipo, operacion, precio in filas],
        columns=["producto", "tipo", "operacion", "fecha", "participaciones", "precio_unitario", "comision"],
    ).astype({"participaciones": "float64"})


def planes_de(compras_df, ventas_df):
    posiciones, operaciones = leer_plan(compras_df, ventas_df)
    return posiciones, calcular_planes(posiciones, operaciones, OtrasRentasAhorro())


def test_un_etf_muestra_su_venta_y_el_traspaso_no_disponible():
    _, planes = planes_de(compras(("ETF", 1000, 20)), ventas(("ETF", "ETF", VENDER, 30)))
    tabla = tabla_comparativa(planes)

    assert list(tabla.columns) == ["Venta del ETF", "Traspaso a otro fondo"]
    assert (tabla["Venta del ETF"][CUOTA], tabla["Venta del ETF"][RETENCION]) == ("1.980,00 €", "0,00 €")
    assert (tabla["Traspaso a otro fondo"] == "No disponible").all()


def test_traspasar_un_etf_explica_que_no_se_puede():
    with pytest.raises(ValueError, match="no admite traspaso"):
        planes_de(compras(("ETF", 1000, 20)), ventas(("ETF", "ETF", TRASPASAR, 30)))


def test_caso_i_dos_fondos_muestra_los_planes_de_referencia_y_el_desglose():
    posiciones, planes = planes_de(
        compras(("Fondo A", 1000, 20), ("Fondo B", 1000, 20)),
        ventas(("Fondo A", FONDO, VENDER, 30), ("Fondo B", FONDO, VENDER, 16)),
    )
    tabla = tabla_comparativa(planes)

    assert list(tabla.columns) == ["Reembolsar o vender todo", "Traspasar los fondos"]
    todo = tabla["Reembolsar o vender todo"]
    assert (todo[CUOTA], todo[RETENCION], todo[EFECTO_RENTA]) == ("1.140,00 €", "1.900,00 €", "-760,00 €")
    assert tabla["Traspasar los fondos"][LATENTE] == "1.140,00 €"

    por_producto = tabla_por_producto(posiciones, planes)
    assert por_producto.loc["Fondo B", "Ganancia o pérdida"] == "-4.000,00 €"
    assert por_producto.loc["Fondo B", "Retención si reembolsas o vendes"] == "0,00 €"
    assert "retenciones superan la cuota" in mensaje_clave(posiciones, planes)


def test_combinar_operaciones_añade_la_columna_tu_seleccion():
    _, planes = planes_de(
        compras(("Fondo A", 1000, 20), ("Fondo B", 1000, 20)),
        ventas(("Fondo A", FONDO, VENDER, 30), ("Fondo B", FONDO, TRASPASAR, 16)),
    )
    tabla = tabla_comparativa(planes)

    assert list(tabla.columns) == ["Tu selección", "Reembolsar o vender todo", "Traspasar los fondos"]
    assert (tabla["Tu selección"][CUOTA], tabla["Tu selección"][LATENTE]) == ("1.980,00 €", "-840,00 €")


def test_venta_de_un_producto_sin_compras_da_error():
    with pytest.raises(ValueError, match="no tiene compras"):
        leer_plan(compras(("Fondo A", 1000, 20)), ventas(("Fondo a", FONDO, VENDER, 30)))


def test_compras_de_productos_que_no_se_venden_no_intervienen():
    posiciones, _ = leer_plan(
        compras(("Fondo A", 1000, 20), ("Fondo C", 50, 10)), ventas(("Fondo A", FONDO, VENDER, 30))
    )
    assert [p.nombre for p in posiciones] == ["Fondo A"]
    assert posiciones[0].venta.participaciones == D("1000")
