---
name: calculo-plusvalias
description: Implementar, modificar o depurar cualquier cálculo del simulador (lotes FIFO, ganancia patrimonial, cuota por tramos de la base del ahorro, retención, comparación de escenarios fondo/traspaso/ETF, compensación de pérdidas). Úsala antes de escribir o cambiar código en simulador/ o sus tests.
---

# Cálculo de plusvalías y escenarios

## Modelo de datos mínimo

```python
@dataclass(frozen=True)
class Lote:
    fecha: date
    participaciones: Decimal
    precio_unitario: Decimal
    comision: Decimal = Decimal("0")

@dataclass(frozen=True)
class Venta:
    fecha: date
    participaciones: Decimal
    precio_unitario: Decimal
    comision: Decimal = Decimal("0")

class TipoProducto(Enum):
    FONDO = "fondo"
    ETF = "etf"
```

## Orden del cálculo (no alterarlo)

1. **Asignar lotes por FIFO** (`lotes.py`): consumir lotes del más antiguo al más reciente. Un lote puede quedar vendido parcialmente; reparte su comisión de compra en proporción a las participaciones vendidas.
2. **Valor de adquisición** = Σ (participaciones vendidas × precio de compra) + comisiones de compra imputables.
3. **Valor de transmisión** = participaciones × precio de venta − comisión de venta.
4. **Ganancia o pérdida** = transmisión − adquisición.
5. **Integrar en la base del ahorro** junto con las demás rentas del ahorro del año que introduzca el usuario (`compensacion.py`, art. 49 LIRPF).
6. **Cuota** aplicando la escala progresiva tramo a tramo (`calculo.py`). Para aislar el efecto de la venta, calcula `cuota(base_con_venta) − cuota(base_sin_venta)`.
7. **Retención** (solo reembolso de fondo): 19 % de la ganancia positiva. Muéstrala por separado y explica que se regulariza en la Renta.
8. Redondea a céntimos solo al final.

## Escenarios (`escenarios.py`)

| Escenario | Ganancia que tributa hoy | Retención | Ganancia diferida |
|---|---|---|---|
| Reembolso de fondo | Toda | 19 % | 0 |
| Traspaso de fondo | 0 | 0 | Toda (impuesto latente) |
| Venta de ETF | Toda | 0 | 0 |

Para el traspaso, devuelve también el **impuesto latente**: la cuota que se pagaría si se reembolsara hoy. Es el dato clave para explicar el diferimiento.

## Tests obligatorios (`tests/`)

Cada función nueva lleva al menos un test con un caso resuelto a mano. Casos de referencia que deben existir siempre:

1. **Ejemplo FIFO de referencia** (Guía Fiscal 2026): lotes de 100 part. a 75 € (2023), 80 part. a 85 € (2024) y 50 part. a 90 € (fecha posterior, ilustrativa). Coste total: 18.800 € por 230 part. Venta de 150 part. a 100 €: valor de transmisión 15.000 €, adquisición FIFO 11.750 €, ganancia 3.250 €, cuota 617,50 € al 19 %. Quedan 80 part. con un coste de 7.050 €.
2. **Cambio de tramo**: base del ahorro de 6.000 € + ganancia de 4.000 € → los 4.000 € tributan al 21 %.
3. **Venta con pérdida** compensada con rendimientos del capital mobiliario, con el límite del 25 %.
4. **Mismo importe en los tres escenarios**: el ETF y el reembolso tienen la misma cuota final; solo cambia la retención. El traspaso tiene cuota 0 e impuesto latente igual a esa cuota.
5. **Venta parcial de un lote**, con reparto proporcional de la comisión.

Ver más casos en [examples.md](examples.md).

## Qué no hacer

- No usar `float` para dinero.
- No mezclar lógica de presentación (textos, formatos €) dentro de `simulador/`.
- No modelizar todavía el régimen transitorio de ETF extranjeros ni la regla de recompra de fondos: solo avisos de texto hasta que estén verificados (skill `normativa-fiscal`).
