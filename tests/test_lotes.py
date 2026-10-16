from datetime import date
from decimal import Decimal

import pytest

from simulador.lotes import Lote, asignar_fifo, valor_adquisicion_total

D = Decimal


def lotes_guia_fiscal() -> list[Lote]:
    """Ejemplo FIFO de referencia (Guía Fiscal 2026). La fecha del tercer lote es ilustrativa."""
    return [
        Lote(date(2023, 3, 1), D("100"), D("75")),
        Lote(date(2024, 3, 1), D("80"), D("85")),
        Lote(date(2025, 3, 1), D("50"), D("90")),
    ]


def test_ejemplo_fifo_de_referencia():
    lotes = lotes_guia_fiscal()
    assert valor_adquisicion_total(lotes) == D("18800")

    asignacion = asignar_fifo(lotes, D("150"))

    # 100 × 75 + 50 × 85 = 7.500 + 4.250
    assert asignacion.valor_adquisicion == D("11750")
    # Quedan 30 × 85 + 50 × 90 = 2.550 + 4.500
    assert sum(lote.participaciones for lote in asignacion.lotes_restantes) == D("80")
    assert valor_adquisicion_total(asignacion.lotes_restantes) == D("7050")


def test_caso_d_venta_parcial_reparte_la_comision_en_proporcion():
    lote = Lote(date(2024, 1, 10), D("100"), D("50"), comision=D("10"))

    asignacion = asignar_fifo([lote], D("40"))

    # 40 × 50 + 10 × 40/100 = 2.000 + 4
    assert asignacion.valor_adquisicion == D("2004")
    (restante,) = asignacion.lotes_restantes
    assert restante.participaciones == D("60")
    assert restante.comision == D("6")


def test_fifo_ordena_por_fecha_aunque_los_lotes_lleguen_desordenados():
    lotes = list(reversed(lotes_guia_fiscal()))
    assert asignar_fifo(lotes, D("150")).valor_adquisicion == D("11750")


def test_vender_todo_no_deja_lotes_restantes():
    asignacion = asignar_fifo(lotes_guia_fiscal(), D("230"))
    assert asignacion.valor_adquisicion == D("18800")
    assert asignacion.lotes_restantes == ()


def test_vender_mas_de_lo_que_hay_en_cartera_da_error():
    with pytest.raises(ValueError, match="solo hay 230"):
        asignar_fifo(lotes_guia_fiscal(), D("231"))


@pytest.mark.parametrize("participaciones", [D("0"), D("-1")])
def test_vender_cero_o_negativo_da_error(participaciones):
    with pytest.raises(ValueError):
        asignar_fifo(lotes_guia_fiscal(), participaciones)


def test_no_se_puede_crear_un_lote_sin_participaciones():
    with pytest.raises(ValueError):
        Lote(date(2024, 1, 1), D("0"), D("10"))
