from datetime import date
from decimal import Decimal

import pytest

from simulador.calculo import (
    calcular_ganancia,
    cuota_ahorro,
    cuota_incremental,
    desglose_cuota,
    redondear_centimos,
    retencion,
)
from simulador.lotes import Lote, TipoProducto, Venta

D = Decimal


def test_caso_a_escala_progresiva():
    # 6.000 × 19 % + 44.000 × 21 % + 10.000 × 23 % = 1.140 + 9.240 + 2.300
    assert cuota_ahorro(D("60000")) == D("12680")


@pytest.mark.parametrize(
    ("base", "cuota"),
    [
        (D("0"), D("0")),
        (D("6000"), D("1140")),  # justo en el límite del primer tramo
        # 1.140 + 9.240 + 34.500 + 27.000. Cuadra con la tabla del art. 66 LIRPF: 35.940 × 2.
        (D("300000"), D("71880")),
        (D("310000"), D("74880")),  # + 10.000 × 30 %
    ],
)
def test_cuota_ahorro_en_los_limites_de_tramo(base, cuota):
    assert cuota_ahorro(base) == cuota


def test_base_negativa_da_error():
    with pytest.raises(ValueError):
        cuota_ahorro(D("-1"))


def test_cambio_de_tramo_la_ganancia_tributa_al_21():
    # Base previa de 6.000 € (primer tramo agotado) + ganancia de 4.000 € → 4.000 × 21 %
    assert cuota_incremental(D("6000"), D("10000")) == D("840")


def test_ejemplo_fifo_de_referencia_ganancia_y_cuota():
    lotes = [
        Lote(date(2023, 3, 1), D("100"), D("75")),
        Lote(date(2024, 3, 1), D("80"), D("85")),
        Lote(date(2025, 3, 1), D("50"), D("90")),
    ]
    venta = Venta(date(2026, 10, 1), D("150"), D("100"))

    resultado = calcular_ganancia(lotes, venta)

    assert resultado.valor_transmision == D("15000")
    assert resultado.valor_adquisicion == D("11750")
    assert resultado.ganancia_patrimonial == D("3250")
    assert cuota_ahorro(resultado.ganancia_patrimonial) == D("617.50")


def test_caso_d_ganancia_con_comisiones():
    lote = Lote(date(2024, 1, 10), D("100"), D("50"), comision=D("10"))
    venta = Venta(date(2026, 10, 1), D("40"), D("60"), comision=D("5"))

    resultado = calcular_ganancia([lote], venta)

    assert resultado.valor_adquisicion == D("2004")
    assert resultado.valor_transmision == D("2395")
    assert resultado.ganancia_patrimonial == D("391")


def test_lote_comprado_despues_de_la_venta_da_error():
    lote = Lote(date(2026, 11, 1), D("10"), D("50"))
    venta = Venta(date(2026, 10, 1), D("10"), D("60"))
    with pytest.raises(ValueError, match="posterior a la venta"):
        calcular_ganancia([lote], venta)


def test_caso_b_retencion_del_reembolso_de_fondo():
    assert retencion(D("10000"), TipoProducto.FONDO) == D("1900")


def test_venta_de_etf_no_lleva_retencion():
    assert retencion(D("10000"), TipoProducto.ETF) == D("0")


@pytest.mark.parametrize("ganancia", [D("0"), D("-500")])
def test_sin_ganancia_no_hay_retencion(ganancia):
    assert retencion(ganancia, TipoProducto.FONDO) == D("0")


@pytest.mark.parametrize(
    ("importe", "redondeado"),
    [(D("0.005"), D("0.01")), (D("0.004"), D("0.00")), (D("617.495"), D("617.50"))],
)
def test_redondeo_a_centimos_half_up(importe, redondeado):
    assert redondear_centimos(importe) == redondeado


# Desglose de la cuota por tramos


def test_desglose_caso_b_dos_tramos():
    # Base de 0 a 10.000: 6.000 × 19 % = 1.140 y 4.000 × 21 % = 840.
    tramos = desglose_cuota(D("0"), D("10000"))
    assert [(t.desde, t.hasta, t.tipo, t.cuota) for t in tramos] == [
        (D("0"), D("6000"), D("0.19"), D("1140")),
        (D("6000"), D("10000"), D("0.21"), D("840")),
    ]
    assert sum(t.cuota for t in tramos) == cuota_incremental(D("0"), D("10000"))


def test_desglose_empezando_a_mitad_de_un_tramo():
    # Base previa de 6.000: los 4.000 € caen enteros en el tramo del 21 %.
    (tramo,) = desglose_cuota(D("6000"), D("10000"))
    assert (tramo.importe, tramo.cuota) == (D("4000"), D("840"))


def test_desglose_hasta_el_ultimo_tramo_abierto():
    tramos = desglose_cuota(D("290000"), D("310000"))
    assert [(t.importe, t.tipo, t.cuota) for t in tramos] == [
        (D("10000"), D("0.27"), D("2700")),
        (D("10000"), D("0.30"), D("3000")),
    ]


def test_desglose_si_la_base_baja_las_cuotas_son_negativas():
    # Caso G: la base pasa de 4.000 a 3.000 → 1.000 × 19 % de ahorro.
    (tramo,) = desglose_cuota(D("4000"), D("3000"))
    assert (tramo.importe, tramo.cuota) == (D("1000"), D("-190"))


def test_desglose_sin_cambio_de_base_esta_vacio():
    assert desglose_cuota(D("5000"), D("5000")) == ()
