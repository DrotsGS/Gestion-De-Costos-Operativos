# Costos de equipos de construcción: fórmula, proyección y agente IA

App web (Streamlit) que estima el costo de dos equipos críticos de una constructora a partir de los precios de sus materias primas X, Y y Z, lo proyecta con rangos de incertidumbre validados con historia y lo traduce a presupuesto y a un verificador de cotizaciones. Un agente de IA (Claude) en el panel lateral responde preguntas sobre los resultados. Prueba técnica de consultoría; el caso se plantea como si "hoy" fuera septiembre de 2023, fin de los datos.

## Hallazgos clave

1. **Equipo 1 = 0,20·X + 0,80·Y; Equipo 2 ≈ ⅓·X + ⅓·Y + ⅓·Z** (R² 0,9997, cointegrados, pesos estables 2010-2023). Como los pesos multiplican precios, Y explica ≈ 96,5 % del costo del Equipo 1 y Z ≈ 77,5 % del Equipo 2.
2. **Z correlaciona 0,84 con el Equipo 1 pero no pesa nada** (p-valor 0,88): las materias primas se mueven juntas y la correlación engaña.
3. **Ningún modelo le gana al último valor.** En el backtest (2016-2023), ARIMA, ETS y promedio móvil no superan con claridad a la caminata aleatoria; el promedio móvil de 3 meses es el peor a 1 mes.
4. **Horizonte confiable: 3 meses** (MAPE ≤ 15 % y cobertura ≥ 65 %). Se proyectan 12 meses como referencia; la cobertura real del rango P10-P90 es ≈ 70 % (nominal 80 %) y se muestra tal cual.
5. **Los datos traían inconsistencias:** un texto oculto en el PDF del caso con conclusiones que los datos contradicen, un atípico en Z (2014-03-25), formatos distintos por archivo y un precio Y que casi nunca cambia. Todo está documentado, no corregido a mano.

## Capturas

> Espacio para capturas de la app y el video del agente (pendiente, lo graba el candidato).

- Resumen ejecutivo: _(captura pendiente)_
- Datos y trampas: _(captura pendiente)_
- Proyección de costos: _(captura pendiente)_
- Video del agente en uso: _(enlace pendiente)_

## Cómo correrla (Windows)

Requisitos: Python 3.14 (probado con 3.14.6). Desde la carpeta del repositorio, en PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app/main.py
```

Se abre en `http://localhost:8501`. La primera carga calcula todos los modelos (~40 s); después queda en caché.

### Agente: Gemini (gratis) o Claude

El agente funciona con Gemini (plan gratuito de Google AI Studio) o con Claude. Sin ninguna key la app funciona igual y el panel muestra conversaciones de ejemplo.

1. Gemini (gratis): entrar a [aistudio.google.com](https://aistudio.google.com), pulsar **Get API key** y crear una key.
2. Ponerla en `.streamlit\secrets.toml` (está en `.gitignore`, no se sube):
   ```toml
   GEMINI_API_KEY = "..."
   ```
   o como variable de entorno: `$env:GEMINI_API_KEY = "..."` (también se acepta `GOOGLE_API_KEY`).
3. Si hay key de Gemini se usa Gemini; si no, `ANTHROPIC_API_KEY` (Claude). Para forzar uno: `PROVEEDOR_AGENTE = "gemini"` o `"claude"`.

El modelo de Gemini por defecto es `gemini-3.5-flash` (si da 404 o 503 se prueba `gemini-3.5-flash-lite`); se cambia con `$env:MODELO_GEMINI = "..."` (otro modelo Flash del plan gratuito). El panel indica qué modelo responde. Con el plan gratuito hay un límite de consultas por minuto: si se supera, el agente avisa y basta esperar un momento. La búsqueda de noticias usa Google Search, que puede no estar incluida en el plan gratuito: en ese caso el agente responde sin noticias y lo avisa.

**API key de Anthropic (opcional, para el agente con Claude).** Sin key la app funciona igual y el panel muestra conversaciones de ejemplo. Para activar el agente, una de dos:

- Crear `.streamlit\secrets.toml` (está en `.gitignore`, no se sube) con:
  ```toml
  ANTHROPIC_API_KEY = "sk-ant-..."
  ```
- O definir la variable de entorno antes de arrancar: `$env:ANTHROPIC_API_KEY = "sk-ant-..."`

El modelo por defecto es `claude-opus-5-5`; se cambia con `$env:MODELO_AGENTE = "..."`.

**Modo rápido** (menos simulaciones y orígenes de backtest; para probar la interfaz, no para leer cifras): `$env:APP_RAPIDO = "1"` antes de `streamlit run`.

## Pruebas

```powershell
.venv\Scripts\python -m pytest            # toda la suite
.venv\Scripts\python -m pytest -W error   # tratando advertencias como errores
```

Cubren carga y limpieza, auditoría, relación, pronóstico, simulación, negocio, pipeline, agente (con un cliente simulado, sin llamar a la API) y pruebas de humo de cada página.

## Estructura del repositorio

```
├── Datos/                 # datos originales del caso (no se modifican; .gitattributes los protege)
├── src/                   # lógica, sin Streamlit
│   ├── utils.py           #   carga, estandarización y limpieza de atípicos
│   ├── auditoria.py       #   hallazgos de calidad de datos
│   ├── relacion.py        #   fórmula (regresión restringida), OLS, VIF, cointegración, pesos móviles
│   ├── pronostico.py      #   modelos, backtest, Monte Carlo (bootstrap por bloques), escenarios
│   ├── negocio.py         #   presupuesto y verificador de cotizaciones
│   ├── pipeline.py        #   build_results(): punto de entrada único para app y agente
│   ├── contenido.py       #   textos fijos (texto oculto, hipótesis X/Y/Z, IA vs agente, supuestos)
│   ├── config.py          #   constantes (fecha del caso, umbrales del horizonte, modelo del agente)
│   └── agente/            #   bucle del agente y sus herramientas
├── app/                   # Streamlit: main.py, layout (secciones y panel del agente), estilo, gráficos, paginas/ (cliente: resumen, proyecciones, presupuesto; análisis: calidad, relacion, validacion, metodologia)
├── tests/                 # pytest
├── scripts/               # grabar_ejemplos.py: graba conversaciones reales del agente
├── docs/
│   ├── informe.md         # informe con los títulos pedidos en el caso
│   ├── DECISIONES.md      # bitácora: qué se probó, qué se descartó y por qué
│   └── arquitectura.md    # arquitectura AWS (diseño, no desplegado) + arquitectura/ con la infografía
└── requirements.txt       # dependencias directas con versión fija
```

## Dónde está cada entregable del caso

| Lo que pide el caso | Dónde está |
|---|---|
| Código funcional | `src/` (lógica con pruebas en `tests/`) y `app/` |
| Fórmula de costo de cada equipo | App: "Qué mueve el precio" · `src/relacion.py` · informe, "Resultados" |
| Proyección con incertidumbre (rangos) | App, sección cliente: "Proyección de costos" (abanico P10/P50/P90, escenarios) · `src/pronostico.py` |
| Horizonte y metodología justificados | App, sección análisis: "Validación de modelos" (backtest, cobertura, prueba con X) · informe, "Proyección de costos y horizonte" · `docs/DECISIONES.md` |
| Uso para el negocio | App: "Presupuesto y proveedores" (P50 + reserva, verificador de cotizaciones) · `src/negocio.py` |
| Agente de IA con conocimiento externo | Panel lateral en todas las páginas · `src/agente/` (herramientas + búsqueda web) |
| IA convencional vs agente | Panel del agente ("¿Qué hace este agente?") y página "Metodología" |
| Arquitectura cloud con diagrama | `docs/arquitectura.md`, `docs/arquitectura/infografia_aws.svg` (diseño, no desplegado; ya no está en la app) |
| Informe con los títulos pedidos | [`docs/informe.md`](docs/informe.md) |
| Repositorio en Markdown | Este README, `docs/` |

## Pendientes del candidato

- [ ] Probar el agente con la API real (key propia) en todas las páginas. Hasta ahora solo se probó con un cliente simulado.
- [ ] Grabar conversaciones reales: `$env:ANTHROPIC_API_KEY = "..."; .venv\Scripts\python scripts\grabar_ejemplos.py` (reemplaza los ejemplos ilustrativos de `app/ejemplos/conversaciones.json`).
- [ ] Grabar el video corto del agente en uso y enlazarlo en la sección "Capturas".
- [ ] Agregar capturas de la app.

## Documentación

- [Informe](docs/informe.md): explicación del caso, supuestos, alternativas, resultados, proyección, mejoras y apreciaciones.
- [Bitácora de decisiones](docs/DECISIONES.md): cada decisión con contexto, opciones, por qué y costo si estuviera mal.
- [Arquitectura AWS](docs/arquitectura.md): diseño propuesto y justificación de cada servicio.
