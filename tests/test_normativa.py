from datetime import date
from decimal import Decimal

from simulador import normativa


def test_escala_ahorro_tiene_limites_crecientes_y_ultimo_tramo_abierto():
    limites = [tramo.hasta for tramo in normativa.ESCALA_AHORRO_2026[:-1]]
    assert limites == sorted(limites)
    assert normativa.ESCALA_AHORRO_2026[-1].hasta is None


def test_escala_ahorro_es_progresiva():
    tipos = [tramo.tipo for tramo in normativa.ESCALA_AHORRO_2026]
    assert tipos == sorted(tipos)


def test_tipos_de_retencion_2026():
    # Art. 101.6 LIRPF y art. 75.3.j RIRPF: misma cuota final, distinta retención.
    assert normativa.TIPO_RETENCION_REEMBOLSO_FONDO == Decimal("0.19")
    assert normativa.TIPO_RETENCION_VENTA_ETF == Decimal("0")


def test_constantes_usadas_en_avisos():
    # Art. 94.2.a).3.º LIRPF y art. 33.5.f y g LIRPF.
    assert normativa.FECHA_EXCLUSION_TRASPASO_ETF_EXTRANJEROS == date(2022, 1, 1)
    assert normativa.PLAZO_RECOMPRA_MESES_MERCADO_REGULADO == 2
    assert normativa.PLAZO_RECOMPRA_MESES_OTROS == 12
