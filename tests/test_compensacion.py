from decimal import Decimal

from simulador.compensacion import ResultadoCompensacion, compensar_base_ahorro

D = Decimal


def test_caso_c_perdida_compensada_con_rendimientos_hasta_el_25():
    # Compensable: 25 % × 4.000 = 1.000. Base: 4.000 − 1.000. Pendiente: 2.000 − 1.000.
    assert compensar_base_ahorro(D("4000"), D("-2000")) == ResultadoCompensacion(
        base_ahorro=D("3000"),
        rendimientos_negativos_pendientes=D("0"),
        perdidas_patrimoniales_pendientes=D("1000"),
    )


def test_caso_e_rendimientos_negativos_compensados_con_ganancias_hasta_el_25():
    assert compensar_base_ahorro(D("-2000"), D("4000")) == ResultadoCompensacion(
        base_ahorro=D("3000"),
        rendimientos_negativos_pendientes=D("1000"),
        perdidas_patrimoniales_pendientes=D("0"),
    )


def test_perdida_que_cabe_en_el_25_se_compensa_entera():
    # Límite: 25 % × 10.000 = 2.500 ≥ 2.000
    resultado = compensar_base_ahorro(D("10000"), D("-2000"))
    assert resultado.base_ahorro == D("8000")
    assert resultado.perdidas_patrimoniales_pendientes == D("0")


def test_dos_saldos_negativos_no_se_compensan_y_quedan_pendientes():
    assert compensar_base_ahorro(D("-300"), D("-2000")) == ResultadoCompensacion(
        base_ahorro=D("0"),
        rendimientos_negativos_pendientes=D("300"),
        perdidas_patrimoniales_pendientes=D("2000"),
    )


def test_dos_saldos_positivos_se_suman():
    resultado = compensar_base_ahorro(D("1500"), D("10000"))
    assert resultado.base_ahorro == D("11500")
    assert resultado.rendimientos_negativos_pendientes == D("0")
    assert resultado.perdidas_patrimoniales_pendientes == D("0")
