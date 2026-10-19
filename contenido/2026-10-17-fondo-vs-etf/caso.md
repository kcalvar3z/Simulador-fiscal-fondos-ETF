# Caso del post: fondo frente a ETF (17-10-2026)

Ficheros: `post.md` (texto para copiar) y `grafico.png` (apaisado, 1200×600 exportado a 2400×1200 px).

## Parámetros

Caso B de `.claude/skills/calculo-plusvalias/examples.md`, definido en `simulador/graficos.py` (`caso_b`):

- Compra: 1.000 participaciones a 20 € el 15-1-2023 (20.000 €), sin comisiones.
- Venta o traspaso: las 1.000 participaciones a 30 € el 16-10-2026 (30.000 €).
- Sin otras rentas del ahorro ni saldos pendientes. IRPF 2026, territorio común.

## Comprobación a mano

| | Reembolso del fondo | Traspaso | Venta del ETF |
|---|---|---|---|
| Ganancia | 10.000 € | 10.000 € (diferida) | 10.000 € |
| Cuota de IRPF en 2026 | 6.000 × 19 % + 4.000 × 21 % = 1.980 € | 0 € | 1.980 € |
| Retención al vender | 19 % × 10.000 = 1.900 € | 0 € | 0 € |
| A ingresar en la Renta | 1.980 − 1.900 = 80 € | 0 € | 1.980 € |
| Impuesto aplazado | — | 1.980 € | — |

## Normativa citada

- Traspaso sin tributar y exclusión de los ETF: art. 94.1.a y 94.2.a LIRPF (ETF extranjeros desde el 1-1-2022, Ley 11/2021).
- Régimen transitorio para ETF extranjeros adquiridos antes del 1-1-2022 y no cotizados en bolsa española: DT 36.ª LIRPF (solo se menciona; el simulador no lo calcula).
- Retención del 19 % en el reembolso: art. 101.6 LIRPF; sin retención en la venta de ETF: art. 75.3.j RIRPF.
- Escala del ahorro: arts. 66 y 76 LIRPF.

## Regenerar el gráfico

```bash
plotly_get_chrome            # una sola vez: Chrome para exportar a PNG
python -m simulador.graficos
```

---

Cálculo orientativo con fines divulgativos. No constituye asesoramiento fiscal ni financiero.
