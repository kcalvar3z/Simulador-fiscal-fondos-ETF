from datetime import date
from decimal import Decimal

import pytest

from simulador.escenarios import comparar_escenarios
from simulador.graficos import DESCRIPCION_CASO_B, PIE, caso_b, euros, figura_fondo_frente_a_etf
from simulador.lotes import Lote, Venta

D = Decimal


@pytest.mark.parametrize(
    ("importe", "texto"),
    [(D("1980"), "1.980 €"), (D("1234567.5"), "1.234.568 €"), (D("0"), "0 €"), (D("79.5"), "80 €")],
)
def test_euros_sin_centimos(importe, texto):
    assert euros(importe) == texto


def test_figura_del_caso_b_dibuja_las_cifras_del_simulador():
    figura = figura_fondo_frente_a_etf(caso_b(), DESCRIPCION_CASO_B)

    # Orden de las barras: reembolso, traspaso, venta de ETF.
    series = {traza.name: list(traza.x) for traza in figura.data}
    assert series == {
        "Retención al vender": [D("1900"), D("0"), D("0")],
        "Pago en la Renta": [D("80"), D("0"), D("1980")],
        "Aplazado con el traspaso": [D("0"), D("1980"), D("0")],
    }
    textos = [anotacion.text for anotacion in figura.layout.annotations]
    assert textos.count("1.980 € este año") == 2
    assert "0 € hoy<br>1.980 € aplazados" in textos
    assert PIE in textos
    assert "no constituye asesoramiento fiscal" in PIE


def test_figura_rechaza_una_venta_con_perdida():
    lotes = [Lote(date(2023, 1, 15), D("1000"), D("20"))]
    venta = Venta(date(2026, 10, 16), D("1000"), D("18"))
    with pytest.raises(ValueError, match="ganancia"):
        figura_fondo_frente_a_etf(comparar_escenarios(lotes, venta), "Caso con pérdida")
