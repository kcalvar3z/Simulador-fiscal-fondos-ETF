from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import AVISO_LEGAL, TRASPASAR, DatosProducto, a_decimal, construir_posicion, formato_euros
from simulador.calculo import calcular_ganancia
from simulador.escenarios import Escenario
from simulador.lotes import TipoProducto

D = Decimal
CUOTA = "Cuota de IRPF en 2026"
RETENCION = "Retención al vender (pago a cuenta)"
EFECTO_RENTA = "Efecto en la Renta (cuota − retención)"
LATENTE = "Impuesto latente (diferido)"
FECHA_VENTA = date(2026, 10, 16)


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


# Construcción de posiciones a partir de lo que rellena el usuario


def ganancia(datos: DatosProducto) -> Decimal:
    posicion = construir_posicion(datos, FECHA_VENTA)
    return calcular_ganancia(posicion.lotes, posicion.venta).ganancia_patrimonial


def datos_sencillos(porcentaje: int = 100) -> DatosProducto:
    return DatosProducto(
        nombre="Mi fondo",
        tipo=TipoProducto.FONDO,
        operacion=Escenario.REEMBOLSO_FONDO,
        invertido=20000.0,
        fecha_compra=date(2023, 1, 15),
        valor_hoy=30000.0,
        porcentaje_vendido=porcentaje,
    )


def test_modo_sencillo_vender_todo():
    assert ganancia(datos_sencillos()) == D("10000")


def test_modo_sencillo_vender_una_parte_reparte_el_coste_en_proporcion():
    # 40 % de 30.000 − 40 % de 20.000 = 12.000 − 8.000
    assert ganancia(datos_sencillos(porcentaje=40)) == D("4000")


def test_modo_detallado_aplica_fifo_ejemplo_de_referencia():
    lotes = pd.DataFrame(
        {
            "fecha": [date(2023, 3, 1), date(2024, 3, 1), date(2025, 3, 1)],
            "participaciones": [100.0, 80.0, 50.0],
            "precio_unitario": [75.0, 85.0, 90.0],
            "comision": [0.0, 0.0, 0.0],
        }
    )
    datos = DatosProducto(
        nombre="Fondo",
        tipo=TipoProducto.FONDO,
        operacion=Escenario.REEMBOLSO_FONDO,
        lotes=lotes,
        participaciones_vendidas=150.0,
        precio_venta=100.0,
    )
    assert ganancia(datos) == D("3250")


def test_inversion_sin_nombre_da_error():
    with pytest.raises(ValueError, match="nombre"):
        construir_posicion(DatosProducto(" ", TipoProducto.FONDO, Escenario.REEMBOLSO_FONDO), FECHA_VENTA)


# App completa


def ejecutar_app() -> AppTest:
    app = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not app.exception
    return app


def tabla_resultados(app: AppTest) -> pd.DataFrame:
    """La tabla comparativa es la que tiene la cuota como fila."""
    return next(tabla.value for tabla in app.dataframe if CUOTA in tabla.value.index)


def test_app_muestra_el_caso_b_por_defecto():
    app = ejecutar_app()
    tabla = tabla_resultados(app)

    assert list(tabla.columns) == ["Reembolso del fondo", "Traspaso a otro fondo"]
    reembolso = tabla["Reembolso del fondo"]
    assert (reembolso[CUOTA], reembolso[RETENCION], reembolso[EFECTO_RENTA]) == ("1.980,00 €", "1.900,00 €", "80,00 €")
    assert tabla["Traspaso a otro fondo"][LATENTE] == "1.980,00 €"
    # Tarjetas de resultado y, en la visualización, ganancia, IRPF y neto del reembolso.
    assert [m.value for m in app.metric] == ["1.980,00 €", "0,00 €", "10.000,00 €", "1.980,00 €", "8.020,00 €"]
    assert any("+40,1 % sobre lo invertido" in c.value for c in app.caption)
    assert any(AVISO_LEGAL in aviso.value for aviso in app.info)


def test_app_con_un_etf_muestra_la_venta_y_el_traspaso_no_disponible():
    app = ejecutar_app()
    app.radio(key="tipo_0").set_value("ETF").run()
    assert not app.exception
    tabla = tabla_resultados(app)

    assert list(tabla.columns) == ["Venta del ETF", "Traspaso a otro fondo"]
    assert tabla["Venta del ETF"][RETENCION] == "0,00 €"
    assert (tabla["Traspaso a otro fondo"] == "No disponible").all()


def test_app_caso_i_añadiendo_un_segundo_fondo():
    app = ejecutar_app()
    app.button(key="anadir").click().run()
    app.text_input(key="nombre_1").set_value("Fondo B")
    app.number_input(key="invertido_1").set_value(20000.0)
    app.number_input(key="valor_hoy_1").set_value(16000.0).run()
    assert not app.exception
    tabla = tabla_resultados(app)

    assert list(tabla.columns) == ["Reembolsar o vender todo", "Traspasar los fondos"]
    todo = tabla["Reembolsar o vender todo"]
    assert (todo[CUOTA], todo[RETENCION], todo[EFECTO_RENTA]) == ("1.140,00 €", "1.900,00 €", "-760,00 €")

    # Reembolsar el que gana y traspasar el que pierde añade la columna «Tu selección».
    app.radio(key="operacion_1").set_value(TRASPASAR).run()
    tabla = tabla_resultados(app)
    assert list(tabla.columns)[0] == "Tu selección"
    assert (tabla["Tu selección"][CUOTA], tabla["Tu selección"][LATENTE]) == ("1.980,00 €", "-840,00 €")
    resumen = next(m.value for m in app.markdown if "**Tu selección:**" in m.value)
    assert "pagas 1.980,00 € de cuota este año" in resumen
    assert "ahorro latente de 840,00 €" in resumen


def test_app_quitar_el_segundo_fondo_vuelve_a_un_solo_producto():
    app = ejecutar_app()
    app.button(key="anadir").click().run()
    app.button(key="quitar_1").click().run()
    assert not app.exception
    assert list(tabla_resultados(app).columns) == ["Reembolso del fondo", "Traspaso a otro fondo"]


def test_app_selector_de_plan_con_el_traspaso_no_hay_cascada():
    app = ejecutar_app()
    app.radio[-1].set_value("Traspaso a otro fondo").run()
    assert not app.exception
    assert any("no vendes nada" in aviso.value and "1.980,00 €" in aviso.value for aviso in app.info)
