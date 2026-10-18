from datetime import date
from decimal import Decimal

import pytest

from simulador.lotes import Lote
from simulador.rentabilidad import rentabilidad

D = Decimal
HOY = date(2026, 10, 16)
PRECISION = D("1e-9")


def test_una_compra_rentabilidad_total_y_anual():
    # 20.000 € el 16-10-2024 que valen 30.000 € dos años después (730 días).
    # Total: +50 %. Anual: 1,5 ^ (1/2) − 1 = 22,4745 %.
    r = rentabilidad([Lote(date(2024, 10, 16), D("1"), D("20000"))], D("30000"), HOY)

    assert (r.invertido, r.valor_actual, r.ganancia, r.total) == (D("20000"), D("30000"), D("10000"), D("0.5"))
    assert abs(r.anual - (D("1.5").sqrt() - 1)) < PRECISION


def test_varias_compras_usa_la_tir():
    # 1.000 € hace dos años y 1.000 € hace uno; hoy valen 2.310 €.
    # Al 10 %: 1.000 × 1,1² + 1.000 × 1,1 = 1.210 + 1.100 = 2.310 → TIR del 10 %.
    lotes = [Lote(date(2024, 10, 16), D("10"), D("100")), Lote(date(2025, 10, 16), D("10"), D("100"))]
    r = rentabilidad(lotes, D("115.5"), HOY)

    assert r.valor_actual == D("2310")
    assert abs(r.anual - D("0.1")) < PRECISION


def test_las_comisiones_de_compra_cuentan_como_invertido():
    r = rentabilidad([Lote(date(2024, 10, 16), D("100"), D("10"), comision=D("20"))], D("12"), HOY)
    assert (r.invertido, r.ganancia) == (D("1020"), D("180"))


def test_perdida_da_rentabilidad_negativa():
    # 20.000 € que valen 16.000 € dos años después: −20 % total; 0,8 ^ (1/2) − 1 = −10,557 % anual.
    r = rentabilidad([Lote(date(2024, 10, 16), D("1"), D("20000"))], D("16000"), HOY)
    assert r.total == D("-0.2")
    assert abs(r.anual - (D("0.8").sqrt() - 1)) < PRECISION


def test_no_se_anualiza_por_debajo_de_un_anio():
    r = rentabilidad([Lote(date(2026, 3, 1), D("1"), D("1000"))], D("1100"), HOY)
    assert r.total == D("0.1")
    assert r.anual is None


def test_compra_posterior_a_la_fecha_da_error():
    with pytest.raises(ValueError):
        rentabilidad([Lote(date(2026, 11, 1), D("1"), D("1000"))], D("1100"), HOY)
