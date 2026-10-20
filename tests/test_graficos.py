from datetime import date
from decimal import Decimal

import pytest

from simulador.compensacion import SaldoPendiente
from simulador.escenarios import Escenario, OtrasRentasAhorro, Posicion, comparar_escenarios, simular_plan
from simulador.graficos import (
    COLOR_APLAZADO,
    COLOR_RENTA,
    COLOR_RETENCION,
    DESCRIPCION_CASO_B,
    PIE,
    caso_b,
    euros,
    figura_caso_a,
    figura_caso_i,
    figura_cascada,
    figura_fondo_frente_a_etf,
    figura_planes,
    figura_rentabilidad,
    pasos_cascada,
    texto_compensacion,
    texto_diferimiento,
)
from simulador.lotes import Lote, TipoProducto, Venta
from simulador.rentabilidad import rentabilidad

D = Decimal


@pytest.mark.parametrize(
    ("importe", "texto"),
    [(D("1980"), "1.980 €"), (D("1234567.5"), "1.234.568 €"), (D("0"), "0 €"), (D("79.5"), "80 €")],
)
def test_euros_sin_centimos(importe, texto):
    assert euros(importe) == texto


def test_figura_del_caso_b_dibuja_las_cifras_del_simulador():
    figura = figura_fondo_frente_a_etf(caso_b(), DESCRIPCION_CASO_B)

    # Orden de las barras: reembolso, traspaso (vacía: hoy no se paga nada), venta de ETF.
    series = {traza.name: list(traza.y) for traza in figura.data}
    assert series == {
        "Retención al vender (pago a cuenta)": [D("1900"), D("0"), D("0")],
        "A ingresar en la declaración de la Renta": [D("80"), D("0"), D("1980")],
    }
    textos = [anotacion.text for anotacion in figura.layout.annotations]
    assert textos.count("1.980 € este año") == 2
    assert "0 € este año" in textos
    # El panel lateral explica el diferimiento con el impuesto latente del simulador.
    assert texto_diferimiento(D("1980")) in textos
    assert "Los 1.980 € no desaparecen" in texto_diferimiento(D("1980"))
    assert PIE in textos
    assert "no constituye asesoramiento fiscal" in PIE


def test_figura_rechaza_una_venta_con_perdida():
    lotes = [Lote(date(2023, 1, 15), D("1000"), D("20"))]
    venta = Venta(date(2026, 10, 16), D("1000"), D("18"))
    with pytest.raises(ValueError, match="ganancia"):
        figura_fondo_frente_a_etf(comparar_escenarios(lotes, venta), "Caso con pérdida")


def series_de(figura) -> dict[str, list]:
    return {traza.name: list(traza.y) for traza in figura.data}


def test_figura_caso_i_dibuja_rayada_la_retencion_que_se_devuelve():
    figura = figura_caso_i()

    # Reembolsar A y B: de los 1.900 € retenidos quedan 1.140 € de cuota y se devuelven 760 €.
    assert series_de(figura) == {
        "Retención al vender (pago a cuenta)": [D("1140"), D("1900"), D("0")],
        "A ingresar en la declaración de la Renta": [D("0"), D("80"), D("0")],
        "Retención que se devuelve en la Renta": [D("760"), D("0"), D("0")],
    }
    textos = [anotacion.text for anotacion in figura.layout.annotations]
    assert {"1.140 € este año", "1.980 € este año", "0 € este año"} <= set(textos)
    assert texto_compensacion(D("10000"), D("4000"), D("1900"), D("760")) in textos
    assert "10.000 € − 4.000 € = 6.000 €" in texto_compensacion(D("10000"), D("4000"), D("1900"), D("760"))


def test_figura_caso_a_desglosa_la_cuota_por_tramos():
    figura = figura_caso_a()

    assert series_de(figura) == {
        "Retención al vender (pago a cuenta)": [D("11400"), D("0"), D("0")],
        "A ingresar en la declaración de la Renta": [D("1280"), D("0"), D("12680")],
    }
    panel = next(anotacion.text for anotacion in figura.layout.annotations if "progresiva" in anotacion.text)
    for linea in [
        "6.000 € al 19 %: 1.140 €",
        "44.000 € al 21 %: 9.240 €",
        "10.000 € al 23 %: 2.300 €",
        "Total: 12.680 €",
        "Los 1.280 € restantes",
        "12.680 € quedan aplazados",
    ]:
        assert linea in panel


def test_figura_planes_rechaza_una_cuota_negativa():
    # Caso G: la pérdida ahorra 190 € de impuesto sobre los intereses.
    plan = simular_plan(
        [posicion("B", "20", "18")],
        {"B": Escenario.REEMBOLSO_FONDO},
        OtrasRentasAhorro(saldo_rendimientos=D("4000")),
    )
    with pytest.raises(ValueError, match="cuota"):
        figura_planes([("Reembolsar B", plan)], "Caso G", "Título", "Panel")


# Gráficos de la app


def posicion(nombre: str, coste_unitario: str, precio_venta: str) -> Posicion:
    lotes = (Lote(date(2023, 1, 15), D("1000"), D(coste_unitario)),)
    return Posicion(nombre, TipoProducto.FONDO, lotes, Venta(date(2026, 10, 16), D("1000"), D(precio_venta)))


def pasos(posiciones, operaciones, otras=OtrasRentasAhorro()):
    return [(p.etiqueta, p.importe, p.total) for p in pasos_cascada(simular_plan(posiciones, operaciones, otras))]


def test_cascada_caso_b_dos_tramos():
    a = posicion("A", "20", "30")
    assert pasos([a], {"A": Escenario.REEMBOLSO_FONDO}) == [
        ("Ganancia · A", D("10000"), False),
        ("IRPF · 6.000 € al 19 %", D("-1140"), False),
        ("IRPF · 4.000 € al 21 %", D("-840"), False),
        ("Neto tras el IRPF", D("8020"), True),
    ]


def test_cascada_caso_i_la_perdida_de_un_fondo_compensa_la_ganancia_del_otro():
    a, b = posicion("A", "20", "30"), posicion("B", "20", "16")
    assert pasos([a, b], {"A": Escenario.REEMBOLSO_FONDO, "B": Escenario.REEMBOLSO_FONDO}) == [
        ("Ganancia · A", D("10000"), False),
        ("Pérdida · B", D("-4000"), False),
        ("Resultado de la venta", D("6000"), True),
        ("IRPF · 6.000 € al 19 %", D("-1140"), False),
        ("Neto tras el IRPF", D("4860"), True),
    ]


def test_cascada_caso_h_las_perdidas_anteriores_ahorran_el_impuesto():
    otras = OtrasRentasAhorro(perdidas_patrimoniales_anteriores=(SaldoPendiente(2022, D("5000")),))
    assert pasos([posicion("A", "20", "21")], {"A": Escenario.REEMBOLSO_FONDO}, otras) == [
        ("Ganancia · A", D("1000"), False),
        ("IRPF · 1.000 € al 19 %", D("-190"), False),
        ("Ahorro por compensaciones", D("190"), False),
        ("Neto tras el IRPF", D("1000"), True),
    ]


def test_cascada_caso_g_perdida_compensada_con_intereses():
    otras = OtrasRentasAhorro(saldo_rendimientos=D("4000"))
    assert pasos([posicion("A", "20", "18")], {"A": Escenario.REEMBOLSO_FONDO}, otras) == [
        ("Pérdida · A", D("-2000"), False),
        ("Ahorro por compensaciones", D("190"), False),
        ("Pérdida tras el IRPF", D("-1810"), True),
    ]


def test_cascada_con_perdida_el_total_no_lleva_el_color_de_los_positivos():
    caso_g = pasos_cascada(
        simular_plan(
            [posicion("A", "20", "18")],
            {"A": Escenario.REEMBOLSO_FONDO},
            OtrasRentasAhorro(saldo_rendimientos=D("4000")),
        )
    )
    (barras,) = figura_cascada(caso_g).data
    # Pérdida (baja), ahorro por compensaciones (sube) y pérdida tras el IRPF (total negativo).
    assert list(barras.marker.color) == [COLOR_RETENCION, COLOR_RENTA, COLOR_RETENCION]
    assert list(barras.base) == [D("0"), D("-2000"), D("0")]


def test_cascada_con_ganancia_el_total_va_en_el_color_de_los_totales():
    caso_b_ = pasos_cascada(simular_plan([posicion("A", "20", "30")], {"A": Escenario.REEMBOLSO_FONDO}))
    (barras,) = figura_cascada(caso_b_).data
    assert list(barras.marker.color) == [COLOR_RENTA, COLOR_RETENCION, COLOR_RETENCION, COLOR_APLAZADO]


def test_cascada_vacia_si_todo_se_traspasa():
    assert pasos([posicion("A", "20", "30")], {"A": Escenario.TRASPASO_FONDO}) == []


def test_figura_rentabilidad_rotula_ganancia_total_y_anual():
    r = rentabilidad([Lote(date(2024, 10, 16), D("1"), D("20000"))], D("30000"), date(2026, 10, 16))
    figura = figura_rentabilidad([("Mi fondo", r)])
    assert [a.text for a in figura.layout.annotations] == ["+10.000 € · +50,0 % · +22,5 % anual"]
    assert [list(traza.x) for traza in figura.data] == [[D("20000")], [D("30000")]]
