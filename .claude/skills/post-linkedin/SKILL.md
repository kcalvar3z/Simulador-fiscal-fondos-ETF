---
name: post-linkedin
description: Redactar publicaciones de LinkedIn y preparar sus gráficos a partir de los resultados del simulador (fondo vs ETF, traspasos, tramos del ahorro). Úsala cuando se pida un post, un carrusel, un gráfico para redes o un texto divulgativo.
---

# Contenido para LinkedIn

El autor es un estudiante de Derecho + ADE que quiere posicionarse en fiscalidad patrimonial. El tono es de **profesional joven que explica con datos**, no de influencer financiero.

## Procedimiento

1. **Parte de un caso calculado con el simulador** (nunca de cifras inventadas). Guarda el script o los parámetros usados en `contenido/AAAA-MM-DD-tema/` para poder reproducirlo.
2. **Comprueba a mano** la cifra principal del post antes de redactar.
3. **Genera el gráfico** con `simulador/graficos.py`:
   - Formato apaisado 1200×600 px, exportado a 2400×1200 px (escala 2) para que se vea nítido, PNG.
   - Estilo de informe analítico: fondo blanco, ejes finos en gris, rejilla suave, leyenda sin recuadro y tipografía sencilla. Usa las constantes `INFORME_*` de `simulador/graficos.py`.
   - Colores validados con la skill `dataviz` en modo claro; nunca rojo y verde juntos (fallan con daltonismo).
   - Una sola idea por gráfico (p. ej. barras con la cuota de hoy en los tres escenarios).
   - Título que sea la conclusión, no la descripción.
   - Fuente y aviso en el pie: "Elaboración propia. IRPF 2026, territorio común. Cálculo orientativo."
4. **Redacta el post** con esta estructura:
   - **Gancho** (1-2 líneas) ligado a la actualidad: "Con la incertidumbre actual, muchos se plantean vender. Antes, conviene saber esto:".
   - **El dato** principal con el caso numérico.
   - **La explicación** en 3-5 líneas o viñetas: qué regla lo causa y su artículo.
   - **La consecuencia práctica**, formulada como información: "Si tienes fondos, existe la opción del traspaso…". Nunca "vende", "compra" ni "deberías".
   - **Cierre** con pregunta abierta o invitación a comentar.
   - **Aviso**: "Contenido divulgativo; no constituye asesoramiento fiscal."
5. Longitud: 150-250 palabras. Sin más de 3 hashtags (p. ej. #Fiscalidad #IRPF #Inversión).
6. Entrega en `contenido/AAAA-MM-DD-tema/post.md` junto con el PNG, y el texto también en la respuesta para copiarlo.

## Reglas

- Español claro, frases cortas, sin jerga innecesaria. Si usas un término técnico (diferimiento, base del ahorro), explícalo en la misma frase.
- Cifras con formato español: 1.980 €, 19 %.
- No mencionar productos, gestoras ni brokers concretos.
- Citar la norma cuando aporte credibilidad (art. 94 LIRPF), sin abusar.
