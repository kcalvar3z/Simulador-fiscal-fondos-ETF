# Caso del post: fondo frente a ETF (17-10-2026)

Ficheros: `post.md` (texto para copiar), `comentario.md` (primer comentario, con el enlace a la app) y un gráfico por escenario, en el orden en que se suben a LinkedIn: `grafico-1-fondo-etf.png`, `grafico-2-compensacion.png` y `grafico-3-tramos.png` (apaisados, 1200×600 exportados a 2400×1200 px).

Supuestos comunes: compras el 15-1-2023 y venta o traspaso el 16-10-2026, sin comisiones, sin otras rentas del ahorro ni saldos pendientes. IRPF 2026, territorio común. Cifras obtenidas con `simulador.escenarios.simular_plan`.

## Escenario 1: una inversión que gana 10.000 €

Caso B de `.claude/skills/calculo-plusvalias/examples.md`, definido en `simulador/graficos.py` (`caso_b`). Gráfico: `grafico-1-fondo-etf.png`. 1.000 participaciones compradas a 20 € (20.000 €) que hoy valen 30 € (30.000 €).

| | Reembolso del fondo | Traspaso | Venta del ETF |
|---|---|---|---|
| Ganancia | 10.000 € | 10.000 € (diferida) | 10.000 € |
| Cuota de IRPF en 2026 | 6.000 × 19 % + 4.000 × 21 % = 1.980 € | 0 € | 1.980 € |
| Retención al vender | 19 % × 10.000 = 1.900 € | 0 € | 0 € |
| A ingresar en la Renta | 1.980 − 1.900 = 80 € | 0 € | 1.980 € |
| Impuesto aplazado | — | 1.980 € | — |

## Escenario 2: un fondo gana 10.000 € y otro pierde 4.000 €

Caso I de `examples.md` (`caso_i`). Gráfico: `grafico-2-compensacion.png`. Fondo A: 20.000 € que hoy valen 30.000 €. Fondo B: 20.000 € que hoy valen 16.000 €.

| | Reembolsar los dos | Reembolsar A y traspasar B | Traspasar los dos |
|---|---|---|---|
| Base del ahorro | 10.000 − 4.000 = 6.000 € | 10.000 € | 0 € |
| Cuota de IRPF en 2026 | 6.000 × 19 % = 1.140 € | 1.980 € | 0 € |
| Retención (fondo a fondo; solo A tiene ganancia) | 1.900 € | 1.900 € | 0 € |
| Efecto en la Renta | 1.140 − 1.900 = −760 € (a devolver) | 80 € | 0 € |
| Impuesto aplazado | — | 1.140 − 1.980 = −840 € (la pérdida de B se aplaza) | 1.140 € |

Si fueran ETF y se vendieran los dos: cuota de 1.140 €, sin retención, toda en la Renta.

## Escenario 3: una inversión que gana 60.000 €

Base del ahorro de 60.000 € (caso A de `examples.md`, `caso_a`): 40.000 € que hoy valen 100.000 €. Gráfico: `grafico-3-tramos.png`.

| | Reembolso del fondo | Traspaso | Venta del ETF |
|---|---|---|---|
| Cuota de IRPF en 2026 | 6.000 × 19 % + 44.000 × 21 % + 10.000 × 23 % = 1.140 + 9.240 + 2.300 = 12.680 € | 0 € | 12.680 € |
| Retención al vender | 19 % × 60.000 = 11.400 € | 0 € | 0 € |
| A ingresar en la Renta | 12.680 − 11.400 = 1.280 € | 0 € | 12.680 € |
| Impuesto aplazado | — | 12.680 € | — |

## Normativa citada

- La revalorización no tributa mientras no se vende: la ganancia patrimonial se imputa al ejercicio de la alteración patrimonial (arts. 14.1.c y 33.1 LIRPF). Los dividendos de fondos o ETF de distribución son rendimientos del capital mobiliario del año en que se cobran (arts. 14.1.a y 25.1.a LIRPF). Excepción no mencionada en el post: los fondos domiciliados en paraísos fiscales imputan cada año la revalorización (art. 95 LIRPF).
- Traspaso sin tributar y exclusión de los ETF: art. 94.1.a y 94.2.a LIRPF (ETF extranjeros desde el 1-1-2022, Ley 11/2021).
- Régimen transitorio para ETF extranjeros adquiridos antes del 1-1-2022 y no cotizados en bolsa española: DT 36.ª LIRPF (solo se menciona; el simulador no lo calcula).
- Retención del 19 % en el reembolso, calculada fondo a fondo: art. 101.6 LIRPF y arts. 96 y 97 RIRPF; sin retención en la venta de ETF: art. 75.3.j RIRPF.
- Compensación de la pérdida con la ganancia del mismo ejercicio: art. 49.1.b LIRPF.
- Escala del ahorro: arts. 66 y 76 LIRPF.

## Regenerar los gráficos

```bash
plotly_get_chrome            # una sola vez: Chrome para exportar a PNG
python -m simulador.graficos
```

---

Cálculo orientativo con fines divulgativos. No constituye asesoramiento fiscal ni financiero.
