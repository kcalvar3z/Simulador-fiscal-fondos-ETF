from datetime import date
from decimal import Decimal

import pytest

from simulador.compensacion import SaldoPendiente
from simulador.escenarios import (
    Aviso,
    Escenario,
    OtrasRentasAhorro,
    Posicion,
    calcular_escenario,
    comparar_escenarios,
    escenarios_disponibles,
    operaciones_reembolsar_todo,
    operaciones_traspasar_fondos,
    simular_plan,
)
from simulador.lotes import Lote, TipoProducto, Venta

D = Decimal
FECHA_VENTA = date(2026, 10, 16)


def inversion(coste_unitario: str, precio_venta: str, fecha_compra: date = date(2023, 1, 15)):
    """1.000 participaciones compradas a `coste_unitario` y vendidas a `precio_venta`."""
    lotes = [Lote(fecha_compra, D("1000"), D(coste_unitario))]
    venta = Venta(FECHA_VENTA, D("1000"), D(precio_venta))
    return lotes, venta


def por_escenario(resultados):
    return {resultado.escenario: resultado for resultado in resultados}


def test_caso_b_comparacion_de_escenarios():
    # 20.000 € que hoy valen 30.000 €: ganancia de 10.000 €.
    # Cuota: 6.000 × 19 % + 4.000 × 21 % = 1.980. Retención del fondo: 19 % × 10.000 = 1.900.
    r = por_escenario(comparar_escenarios(*inversion("20", "30")))

    reembolso = r[Escenario.REEMBOLSO_FONDO]
    assert (reembolso.cuota, reembolso.retencion, reembolso.impuesto_latente) == (D("1980"), D("1900"), D("0"))
    assert reembolso.regularizacion_renta == D("80")

    traspaso = r[Escenario.TRASPASO_FONDO]
    assert (traspaso.cuota, traspaso.retencion, traspaso.impuesto_latente) == (D("0"), D("0"), D("1980"))

    etf = r[Escenario.VENTA_ETF]
    assert (etf.cuota, etf.retencion, etf.impuesto_latente) == (D("1980"), D("0"), D("0"))
    assert etf.regularizacion_renta == D("1980")

    assert all(resultado.ganancia_patrimonial == D("10000") for resultado in r.values())


def test_misma_cuota_en_reembolso_y_etf_y_latente_igual_en_traspaso():
    # Con 3.000 € de intereses: cuota sin venta 570; con venta (13.000) 1.140 + 7.000 × 21 % = 2.610.
    # Cuota atribuible a la venta: 2.610 − 570 = 2.040.
    otras = OtrasRentasAhorro(saldo_rendimientos=D("3000"))
    r = por_escenario(comparar_escenarios(*inversion("20", "30"), otras))

    assert r[Escenario.REEMBOLSO_FONDO].cuota == r[Escenario.VENTA_ETF].cuota == D("2040")
    assert r[Escenario.TRASPASO_FONDO].impuesto_latente == D("2040")
    assert r[Escenario.REEMBOLSO_FONDO].retencion != r[Escenario.VENTA_ETF].retencion


def test_cambio_de_tramo_la_ganancia_tributa_al_21():
    # 6.000 € de intereses agotan el primer tramo: 4.000 × 21 % = 840. Retención: 760. Regulariza 80.
    otras = OtrasRentasAhorro(saldo_rendimientos=D("6000"))
    reembolso = calcular_escenario(Escenario.REEMBOLSO_FONDO, *inversion("20", "24"), otras)

    assert reembolso.cuota == D("840")
    assert reembolso.retencion == D("760")
    assert reembolso.regularizacion_renta == D("80")


def test_caso_g_venta_con_perdida_compensada_con_rendimientos():
    # Pérdida de 2.000 € con 4.000 € de intereses: compensa 1.000 (25 %), base 3.000.
    # Cuota sin venta 760; con venta 570: la venta ahorra 190. Pendiente: 1.000 € de 2026.
    otras = OtrasRentasAhorro(saldo_rendimientos=D("4000"))
    r = por_escenario(comparar_escenarios(*inversion("20", "18"), otras))

    reembolso = r[Escenario.REEMBOLSO_FONDO]
    assert (reembolso.cuota, reembolso.retencion) == (D("-190"), D("0"))
    assert reembolso.compensacion.perdidas_patrimoniales_pendientes == (SaldoPendiente(2026, D("1000")),)
    assert Aviso.REGLA_RECOMPRA in reembolso.avisos

    # En el traspaso la pérdida también se difiere: el ahorro de 190 € queda latente.
    traspaso = r[Escenario.TRASPASO_FONDO]
    assert (traspaso.cuota, traspaso.impuesto_latente) == (D("0"), D("-190"))
    assert Aviso.REGLA_RECOMPRA not in traspaso.avisos


def test_caso_h_reembolso_aprovecha_perdidas_que_caducan_y_el_traspaso_no():
    # Pérdidas de 2022 pendientes: 5.000 € (2026 es su último año). Ganancia de la venta: 1.000 €.
    # Reembolso: compensa 1.000 → cuota 0, pero retiene 190 que se devuelven en la Renta; caducan 4.000.
    # Traspaso: no hay ganancia que compensar → caducan los 5.000.
    otras = OtrasRentasAhorro(perdidas_patrimoniales_anteriores=(SaldoPendiente(2022, D("5000")),))
    r = por_escenario(comparar_escenarios(*inversion("20", "21"), otras))

    reembolso = r[Escenario.REEMBOLSO_FONDO]
    assert (reembolso.cuota, reembolso.retencion, reembolso.regularizacion_renta) == (D("0"), D("190"), D("-190"))
    assert reembolso.compensacion.perdidas_patrimoniales_caducadas == D("4000")

    traspaso = r[Escenario.TRASPASO_FONDO]
    assert traspaso.impuesto_latente == D("0")
    assert traspaso.compensacion.perdidas_patrimoniales_caducadas == D("5000")
    assert Aviso.SALDOS_CADUCADOS in traspaso.avisos


def test_un_etf_no_admite_traspaso():
    assert escenarios_disponibles(TipoProducto.ETF) == (Escenario.VENTA_ETF,)
    assert escenarios_disponibles(TipoProducto.FONDO) == (Escenario.REEMBOLSO_FONDO, Escenario.TRASPASO_FONDO)


def test_aviso_de_regimen_transitorio_solo_para_etf_con_lotes_anteriores_a_2022():
    lotes, venta = inversion("20", "30", fecha_compra=date(2021, 6, 1))
    r = por_escenario(comparar_escenarios(lotes, venta))

    assert Aviso.REGIMEN_TRANSITORIO_ETF in r[Escenario.VENTA_ETF].avisos
    assert Aviso.REGIMEN_TRANSITORIO_ETF not in r[Escenario.REEMBOLSO_FONDO].avisos


def test_sin_situaciones_especiales_no_hay_avisos():
    assert all(resultado.avisos == () for resultado in comparar_escenarios(*inversion("20", "30")))


def test_venta_fuera_del_ejercicio_2026_da_error():
    lotes = [Lote(date(2023, 1, 15), D("10"), D("20"))]
    venta = Venta(date(2025, 12, 31), D("10"), D("30"))
    with pytest.raises(ValueError, match="2026"):
        calcular_escenario(Escenario.VENTA_ETF, lotes, venta)


# Planes con varias posiciones


def posicion(nombre: str, tipo: TipoProducto, coste_unitario: str, precio_venta: str) -> Posicion:
    lotes, venta = inversion(coste_unitario, precio_venta)
    return Posicion(nombre, tipo, tuple(lotes), venta)


def caso_i() -> list[Posicion]:
    # Fondo A: 20.000 → 30.000 (gana 10.000). Fondo B: 20.000 → 16.000 (pierde 4.000).
    return [posicion("Fondo A", TipoProducto.FONDO, "20", "30"), posicion("Fondo B", TipoProducto.FONDO, "20", "16")]


def test_caso_i_reembolsar_todo_la_retencion_es_fondo_a_fondo():
    # Base: 10.000 − 4.000 = 6.000 → cuota 1.140. Retención solo de A: 19 % × 10.000 = 1.900.
    # La retención no descuenta la pérdida de B: en la Renta se devuelven 760.
    posiciones = caso_i()
    plan = simular_plan(posiciones, operaciones_reembolsar_todo(posiciones))

    assert (plan.cuota, plan.retencion, plan.regularizacion_renta, plan.impuesto_latente) == (
        D("1140"),
        D("1900"),
        D("-760"),
        D("0"),
    )
    assert [p.retencion for p in plan.posiciones] == [D("1900"), D("0")]
    assert plan.posiciones[1].avisos == (Aviso.REGLA_RECOMPRA,)


def test_caso_i_traspasar_todo_difiere_la_cuota_conjunta():
    posiciones = caso_i()
    plan = simular_plan(posiciones, operaciones_traspasar_fondos(posiciones))

    assert (plan.cuota, plan.retencion, plan.impuesto_latente) == (D("0"), D("0"), D("1140"))


def test_caso_i_reembolsar_el_que_gana_y_traspasar_el_que_pierde():
    # Hoy tributa A sola: 6.000 × 19 % + 4.000 × 21 % = 1.980.
    # Latente: cuota si se reembolsara todo (1.140) − cuota de hoy (1.980) = −840: la pérdida diferida
    # de B es un ahorro futuro.
    plan = simular_plan(
        caso_i(), {"Fondo A": Escenario.REEMBOLSO_FONDO, "Fondo B": Escenario.TRASPASO_FONDO}
    )

    assert (plan.cuota, plan.retencion, plan.impuesto_latente) == (D("1980"), D("1900"), D("-840"))


def test_caso_i_reembolsar_el_que_pierde_y_traspasar_el_que_gana():
    # Hoy solo se computa la pérdida de B: base 0, cuota 0, y 4.000 € quedan pendientes.
    plan = simular_plan(
        caso_i(), {"Fondo A": Escenario.TRASPASO_FONDO, "Fondo B": Escenario.REEMBOLSO_FONDO}
    )

    assert (plan.cuota, plan.retencion, plan.impuesto_latente) == (D("0"), D("0"), D("1140"))
    assert plan.compensacion.perdidas_patrimoniales_pendientes == (SaldoPendiente(2026, D("4000")),)


def test_traspasar_los_fondos_vende_igualmente_los_etf():
    # ETF: gana 5.000 y se vende → cuota 950, sin retención. Fondo: gana 5.000 y se traspasa.
    # Latente: cuota de 10.000 (1.980) − cuota de hoy (950) = 1.030.
    posiciones = [posicion("ETF", TipoProducto.ETF, "20", "25"), posicion("Fondo", TipoProducto.FONDO, "20", "25")]
    operaciones = operaciones_traspasar_fondos(posiciones)
    assert operaciones == {"ETF": Escenario.VENTA_ETF, "Fondo": Escenario.TRASPASO_FONDO}

    plan = simular_plan(posiciones, operaciones)
    assert (plan.cuota, plan.retencion, plan.impuesto_latente) == (D("950"), D("0"), D("1030"))


def test_un_etf_no_se_puede_traspasar_en_un_plan():
    posiciones = [posicion("ETF", TipoProducto.ETF, "20", "25")]
    with pytest.raises(ValueError, match="no admite traspaso"):
        simular_plan(posiciones, {"ETF": Escenario.TRASPASO_FONDO})


def test_un_fondo_no_se_vende_como_etf():
    posiciones = [posicion("Fondo", TipoProducto.FONDO, "20", "25")]
    with pytest.raises(ValueError, match="es un fondo"):
        simular_plan(posiciones, {"Fondo": Escenario.VENTA_ETF})


def test_nombres_repetidos_dan_error():
    posiciones = [posicion("A", TipoProducto.FONDO, "20", "25"), posicion("A", TipoProducto.FONDO, "20", "30")]
    with pytest.raises(ValueError, match="mismo nombre"):
        simular_plan(posiciones, {"A": Escenario.REEMBOLSO_FONDO})


def test_falta_la_operacion_de_una_posicion():
    posiciones = caso_i()
    with pytest.raises(ValueError, match="Fondo B"):
        simular_plan(posiciones, {"Fondo A": Escenario.REEMBOLSO_FONDO})
