from decimal import Decimal

import pytest

from simulador.compensacion import ResultadoCompensacion, SaldoPendiente, compensar_base_ahorro

D = Decimal


# Saldos del propio ejercicio (2026)


def test_caso_c_perdida_compensada_con_rendimientos_hasta_el_25():
    # Compensable: 25 % × 4.000 = 1.000. Base: 4.000 − 1.000. Pendiente: 2.000 − 1.000.
    assert compensar_base_ahorro(D("4000"), D("-2000")) == ResultadoCompensacion(
        base_ahorro=D("3000"),
        perdidas_patrimoniales_pendientes=(SaldoPendiente(2026, D("1000")),),
    )


def test_caso_e_rendimientos_negativos_compensados_con_ganancias_hasta_el_25():
    assert compensar_base_ahorro(D("-2000"), D("4000")) == ResultadoCompensacion(
        base_ahorro=D("3000"),
        rendimientos_negativos_pendientes=(SaldoPendiente(2026, D("1000")),),
    )


def test_perdida_que_cabe_en_el_25_se_compensa_entera():
    # Límite: 25 % × 10.000 = 2.500 ≥ 2.000
    assert compensar_base_ahorro(D("10000"), D("-2000")) == ResultadoCompensacion(base_ahorro=D("8000"))


def test_dos_saldos_negativos_no_se_compensan_y_quedan_pendientes():
    assert compensar_base_ahorro(D("-300"), D("-2000")) == ResultadoCompensacion(
        base_ahorro=D("0"),
        rendimientos_negativos_pendientes=(SaldoPendiente(2026, D("300")),),
        perdidas_patrimoniales_pendientes=(SaldoPendiente(2026, D("2000")),),
    )


def test_dos_saldos_positivos_se_suman():
    assert compensar_base_ahorro(D("1500"), D("10000")) == ResultadoCompensacion(base_ahorro=D("11500"))


# Saldos pendientes de ejercicios anteriores


def test_caso_f_caso_practico_aeat_con_saldos_de_ejercicios_anteriores():
    # Manual de Renta 2025, cap. 12, con los ejercicios desplazados un año.
    resultado = compensar_base_ahorro(
        saldo_rendimientos=D("-800"),
        saldo_ganancias_perdidas=D("4000"),  # 5.600 − 1.600
        rendimientos_negativos_anteriores=[SaldoPendiente(2022, D("500"))],
        perdidas_patrimoniales_anteriores=[
            SaldoPendiente(2022, D("700")),
            SaldoPendiente(2023, D("2100")),
        ],
    )
    # Cupo: 25 % × 4.000 = 1.000 → 800 de 2026 + 200 de 2022.
    # Ganancias: 4.000 − 800 − 700 − 2.100 − 200 = 200.
    # Los 300 € de rendimientos negativos de 2022 no compensados caducan en 2026.
    assert resultado == ResultadoCompensacion(
        base_ahorro=D("200"),
        rendimientos_negativos_caducados=D("300"),
    )


def test_perdidas_anteriores_contra_ganancias_del_año_no_tienen_limite():
    resultado = compensar_base_ahorro(
        D("0"), D("5000"), perdidas_patrimoniales_anteriores=[SaldoPendiente(2024, D("3000"))]
    )
    assert resultado == ResultadoCompensacion(base_ahorro=D("2000"))


def test_se_compensan_primero_los_ejercicios_mas_antiguos():
    resultado = compensar_base_ahorro(
        D("0"),
        D("1000"),
        perdidas_patrimoniales_anteriores=[
            SaldoPendiente(2024, D("800")),
            SaldoPendiente(2023, D("800")),
        ],
    )
    assert resultado == ResultadoCompensacion(
        base_ahorro=D("0"),
        perdidas_patrimoniales_pendientes=(SaldoPendiente(2024, D("600")),),
    )


def test_el_limite_del_25_es_conjunto_para_el_ejercicio_y_los_anteriores():
    # Cupo: 25 % × 4.000 = 1.000 → 600 de 2026 y solo 400 de los 1.000 de 2023.
    resultado = compensar_base_ahorro(
        D("4000"), D("-600"), perdidas_patrimoniales_anteriores=[SaldoPendiente(2023, D("1000"))]
    )
    assert resultado == ResultadoCompensacion(
        base_ahorro=D("3000"),
        perdidas_patrimoniales_pendientes=(SaldoPendiente(2023, D("600")),),
    )


def test_saldo_del_cuarto_año_anterior_no_compensado_caduca():
    resultado = compensar_base_ahorro(
        D("0"), D("0"), perdidas_patrimoniales_anteriores=[SaldoPendiente(2022, D("500"))]
    )
    assert resultado == ResultadoCompensacion(base_ahorro=D("0"), perdidas_patrimoniales_caducadas=D("500"))


@pytest.mark.parametrize("ejercicio", [2021, 2026])
def test_saldo_anterior_fuera_del_plazo_de_cuatro_años_da_error(ejercicio):
    with pytest.raises(ValueError, match="de 2022 a 2025"):
        compensar_base_ahorro(
            D("0"), D("0"), perdidas_patrimoniales_anteriores=[SaldoPendiente(ejercicio, D("100"))]
        )


def test_saldo_anterior_debe_indicarse_en_positivo():
    with pytest.raises(ValueError):
        compensar_base_ahorro(
            D("0"), D("0"), rendimientos_negativos_anteriores=[SaldoPendiente(2024, D("-100"))]
        )


def test_dos_saldos_del_mismo_ejercicio_dan_error():
    with pytest.raises(ValueError):
        compensar_base_ahorro(
            D("0"),
            D("0"),
            perdidas_patrimoniales_anteriores=[SaldoPendiente(2024, D("100")), SaldoPendiente(2024, D("50"))],
        )
