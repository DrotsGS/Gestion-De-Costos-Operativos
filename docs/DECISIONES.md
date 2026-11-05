# Bitácora de decisiones

Registro de lo que se probó, lo que se descartó y lo que se eligió, en orden cronológico. Cada entrada sigue el formato **Contexto · Opciones · Decisión · Por qué · Costo si estuviera mal**. Los números salen del código (`build_results()` con la configuración de producción: backtest con origen mensual desde 2016-01 y 5.000 simulaciones).

Índice:

1. [Frecuencia mensual](#2026-10-31---frecuencia-de-trabajo-mensual)
2. [Regla de atípicos combinada](#2026-10-31---regla-de-atípicos-combinada)
3. [Fines de línea de `Datos/`](#2026-10-31---fines-de-línea-de-datos)
4. [PDF del caso fuera del repositorio](#2026-10-31---pdf-del-caso-fuera-del-repositorio)
5. [Regresión restringida](#2026-10-31---fórmula-de-costo-con-regresión-restringida)
6. [Modelos de pronóstico comparados y ganador](#2026-10-31---modelos-de-pronóstico-comparados-y-ganador)
7. [Simulación: gaussiana → bootstrap por bloques](#2026-10-31---simulación-bootstrap-por-bloques-en-lugar-de-normal)
8. [Aceptar cobertura ≈ 70 % y mostrarla](#2026-10-31---aceptar-una-cobertura-cercana-al-70--y-mostrarla)
9. [Horizonte y umbrales](#2026-11-01---horizonte-confiable-y-umbrales)
10. [Ruido diario vs. mensual](#2026-11-01---ruido-diario-vs-mensual-en-presupuesto-y-cotizaciones)
11. [Cantidades de ejemplo](#2026-11-01---cantidades-de-ejemplo-en-el-presupuesto)
12. [Streamlit](#2026-11-01---streamlit-como-interfaz)
13. [Agente de IA](#2026-11-01---agente-de-ia-modelo-herramientas-historial-y-respaldo)
14. [AWS diseñado, no desplegado](#2026-11-01---arquitectura-aws-diseñada-pero-no-desplegada)

---

## 2026-10-31 - Frecuencia de trabajo mensual

**Contexto.** Los datos son diarios (días hábiles, 2010-01-04 a 2023-08-31). Y tiene 282 tramos de 5 o más días con el mismo valor (máximo 35 días, desde 2014-01-17): parece un precio publicado cada cierto tiempo y repetido día a día. El presupuesto de una constructora se arma por mes.

**Opciones.** (a) Diaria. (b) Semanal. (c) Mensual (promedio del mes).

**Decisión.** Mensual (promedio del mes, índice al inicio del mes; 164 meses de 2010-01 a 2023-08). Lo diario se usa solo en la auditoría.

**Por qué.** Con frecuencia diaria, los cambios de Y son casi siempre cero y la correlación de cambios diarios engaña. El promedio mensual elimina ese artefacto y coincide con la unidad de decisión del negocio. Además, el ruido del residuo baja de ≈ 1,8 % diario a ≈ 0,3-0,4 % mensual.

**Costo si estuviera mal.** Se perdería información intra-mes (por ejemplo, para fijar el día óptimo de compra). Se mitiga advirtiendo que una compra puntual tiene ≈ 1,8 % de ruido adicional (ver entrada 10).

## 2026-10-31 - Regla de atípicos combinada

**Contexto.** Z vale `1911,9672592592592` el 2014-03-25. Es el único valor con más de 2 decimales y salta 1.688,25 → 1.911,97 → 1.705,25. X también tiene picos que se revierten (1990-10-02, 2015-08-31, 2020-03-18), pero coinciden con eventos de mercado reales y tienen 2 decimales.

**Opciones.** (a) Corregir a mano la fecha conocida. (b) Corregir todo pico que se revierte (> 8 % ida y vuelta). (c) Corregir solo si se cumplen **ambas** condiciones: pico revertido > 8 % **y** precisión decimal anómala; si se cumple solo una, advertir.

**Decisión.** (c), en `src/utils.py` (`detect_anomalies` y `clean_series`). El punto corregido se reemplaza por interpolación lineal en el tiempo (Z 2014-03-25: 1.911,97 → 1.696,75). Cada corrección queda registrada y se muestra en la página "Datos y trampas". `Datos/` nunca se edita.

**Por qué.** Una regla genérica sirve con datos nuevos, a diferencia de fijar la fecha a mano. Exigir las dos señales evita borrar eventos reales como la caída del COVID en marzo de 2020.

**Costo si estuviera mal.** Bajo: es un solo día de 3.530; en el promedio mensual de marzo de 2014 su efecto es ≈ 0,6 %. Si la regla fuera demasiado estricta, otro atípico pasaría sin corregir, pero quedaría igual en la lista de advertencias.

## 2026-10-31 - Fines de línea de `Datos/`

**Contexto.** Al crear el repositorio, Git normalizó por accidente los fines de línea de X.csv, Y.csv y Z.csv: los archivos versionados dejaron de ser idénticos byte a byte a los originales.

**Opciones.** (a) Ignorarlo (pandas lee igual). (b) Restaurar los bytes originales y proteger la carpeta.

**Decisión.** (b): se restauraron los originales y se agregó `Datos/** -text` en `.gitattributes`.

**Por qué.** La regla del proyecto es que los datos de entrada no se tocan. Un evaluador que compare hashes debe ver los mismos archivos que entregó.

**Costo si estuviera mal.** Ninguno funcional; solo una línea extra en `.gitattributes`.

## 2026-10-31 - PDF del caso fuera del repositorio

**Contexto.** El PDF del enunciado está en la raíz de la carpeta de trabajo y contiene un texto oculto (ver `docs/informe.md`, "Apreciaciones").

**Opciones.** (a) Versionarlo. (b) Dejarlo fuera de Git y resumir en la documentación lo relevante.

**Decisión.** (b): `/*.pdf` en `.gitignore`.

**Por qué.** Es material del evaluador, no un producto del candidato; no hace falta para correr la app. Lo relevante (requisitos y el texto oculto) queda descrito en el informe.

**Costo si estuviera mal.** Bajo: si el evaluador quisiera el PDF en el repo, basta con agregarlo.

## 2026-10-31 - Fórmula de costo con regresión restringida

**Contexto.** Hay que expresar el costo de cada equipo en función de X, Y y Z de forma explicable y estable. Las tres materias primas están correlacionadas entre sí (corr. Y-Z = 0,85).

**Opciones.** (a) OLS libre con intercepto. (b) Regresión restringida: pesos ≥ 0 que suman 1, sin intercepto. (c) Modelos no lineales o de aprendizaje automático.

**Decisión.** (b) como fórmula oficial (`fit_constrained`, optimizador SLSQP con validación de convergencia), y (a) como respaldo estadístico (p-valores, R², VIF).

Resultado (mensual 2010-01 a 2023-08):

| Equipo | Fórmula restringida | OLS: p-valor de Z | R² (OLS) | Cointegración (Engle-Granger, p) | Pesos móviles 36 meses |
|---|---|---|---|---|---|
| Equipo 1 | 0,200·X + 0,800·Y + 0,000·Z | 0,88 | 0,9997 | 7,7·10⁻²⁰ | Y entre 0,782 y 0,801 |
| Equipo 2 | 0,332·X + 0,335·Y + 0,333·Z | ≈ 10⁻²²¹ | 0,9997 | 4,2·10⁻²⁴ | cada peso entre 0,31 y 0,36 |

**Por qué.** La fórmula restringida es una media ponderada de precios fácil de leer y casi coincide con OLS libre (E1: 0,198 X + 0,801 Y − 0,0001 Z, intercepto no significativo, p = 0,97), así que la restricción no fuerza nada. La cointegración descarta una regresión espuria entre series con tendencia. Los pesos móviles muestran que la relación es estable en el tiempo. Los desfases no aportan: el R² baja de 0,9997 (sin desfase) a 0,94 con 1 mes. Ojo: los pesos multiplican precios de distinta escala; con precios de agosto 2023, Y explica ≈ 96,5 % del costo del Equipo 1 y Z ≈ 77 % del Equipo 2 (pesos iguales, pero Z cuesta ≈ 2.133 frente a ≈ 556 de Y y ≈ 85 de X).

**Costo si estuviera mal.** Si la relación real cambiara (otro proveedor, otra receta), la fórmula quedaría obsoleta. Se mitiga con los pesos móviles, que en una versión productiva servirían como alerta.

## 2026-10-31 - Modelos de pronóstico comparados y ganador

**Contexto.** Hay que pronosticar X, Y y Z (y con la fórmula, los equipos) y demostrar con datos qué modelo usar. El texto oculto del PDF pide usar solo un promedio móvil de 3 meses.

**Opciones.** Caminata aleatoria (último valor), promedio móvil de 3 meses (SMA3), ARIMA(1,1,0) en log, ETS con tendencia amortiguada en log. VAR/VECM quedó en el plan como opcional y no se implementó (ver "Por qué").

**Decisión.** Caminata aleatoria en log sin deriva como modelo central, simulada con Monte Carlo (entrada 7).

Backtest de origen móvil (origen mensual desde 2016-01, se ajusta solo con datos anteriores al origen), MAPE por horizonte en meses:

| Equipo | Modelo | 1 | 3 | 6 | 9 | 12 |
|---|---|---|---|---|---|---|
| Equipo 1 | Caminata aleatoria | 5,0 % | 11,4 % | 15,4 % | 19,1 % | 24,5 % |
| Equipo 1 | ARIMA(1,1,0) | 4,9 % | 11,9 % | 16,3 % | 18,6 % | 24,2 % |
| Equipo 1 | ETS amortiguado | 5,3 % | 13,4 % | 18,3 % | 20,0 % | 26,3 % |
| Equipo 1 | Promedio móvil 3 m | 7,8 % | 12,6 % | 16,0 % | 20,7 % | 26,3 % |
| Equipo 2 | Caminata aleatoria | 3,6 % | 8,1 % | 12,2 % | 15,9 % | 19,9 % |
| Equipo 2 | ARIMA(1,1,0) | 3,5 % | 7,9 % | 12,1 % | 15,4 % | 19,5 % |
| Equipo 2 | ETS amortiguado | 3,6 % | 8,3 % | 12,5 % | 15,8 % | 20,3 % |
| Equipo 2 | Promedio móvil 3 m | 5,6 % | 9,2 % | 13,2 % | 17,2 % | 21,0 % |

**Por qué.** ARIMA queda a menos de 1 pp de la caminata aleatoria en todos los horizontes, a veces mejor y a veces peor: no hay estructura que explotar, los precios se comportan como una caminata aleatoria. Ante empate, se elige el modelo más simple y fácil de defender. ETS es algo peor y SMA3 es el peor a 1 mes (7,8 % vs 5,0 % en E1), lo que contradice al texto oculto. VAR/VECM se dejó para después porque, si un ARIMA univariado no le gana al último valor, es poco probable que un modelo conjunto lo haga en el pronóstico central; lo que sí aporta un modelo conjunto (respetar la correlación entre materias primas) ya lo cubre el bootstrap conjunto.

**Costo si estuviera mal.** Si existiera una tendencia predecible, la caminata aleatoria la ignoraría. El backtest se rehace con cada dato nuevo y mostraría si ARIMA o ETS empiezan a ganar.

## 2026-10-31 - Simulación: bootstrap por bloques en lugar de normal

**Contexto.** El abanico P10-P90 con shocks normales iid (covarianza de 10 años) cubría muy por debajo del 80 % nominal (Equipo2 h=12: 48 %). Causas probables: retornos mensuales autocorrelacionados y colas pesadas / regímenes de volatilidad.

**Opciones** (cobertura P10-P90 fuera de muestra, origen móvil mensual desde 2016-01, 1000 trayectorias, pesos restringidos; nominal 0.80):

| Equipo | Configuración | h=1 | h=3 | h=6 | h=9 | h=12 | media |
|---|---|---|---|---|---|---|---|
| Equipo1 | normal (10 años) | 0.783 | 0.600 | 0.655 | 0.679 | 0.593 | 0.662 |
| Equipo1 | bootstrap bloque 3 | 0.696 | 0.722 | 0.701 | 0.714 | 0.716 | 0.710 |
| Equipo1 | bootstrap bloque 6 | 0.707 | 0.722 | 0.736 | 0.690 | 0.667 | 0.704 |
| Equipo1 | bootstrap bloque 12 | 0.717 | 0.711 | 0.713 | 0.702 | 0.691 | 0.707 |
| Equipo2 | normal (10 años) | 0.696 | 0.622 | 0.609 | 0.500 | 0.481 | 0.582 |
| Equipo2 | bootstrap bloque 3 | 0.717 | 0.689 | 0.690 | 0.619 | 0.568 | 0.657 |
| Equipo2 | bootstrap bloque 6 | 0.707 | 0.689 | 0.724 | 0.679 | 0.617 | 0.683 |
| Equipo2 | bootstrap bloque 12 | 0.717 | 0.678 | 0.713 | 0.679 | 0.568 | 0.671 |

Variantes con solo 5 o 10 años de historia (bloques 6 y 12) no mejoraron (peor caso 0.58-0.62 en Equipo2 h=12).

**Decisión.** Bootstrap de bloques móviles de 6 meses sobre toda la historia previa al origen (filas X,Y,Z juntas, retornos centrados = sin deriva). Es la mejor media y el mejor peor caso entre las opciones. `method="normal"` se conserva para comparar.

**Por qué.** Remuestrear bloques del vector conjunto de retornos conserva la correlación entre materias primas y la autocorrelación de corto plazo sin suponer una distribución. Centrar los retornos evita inventar una deriva.

**Límite honesto.** Ninguna configuración llega a 0.80; la cobertura queda en ~0.62-0.74 (Equipo2 h=12: 0.62), es decir, el abanico sigue algo estrecho a horizontes largos. Se reporta tal cual, sin ajustar la prueba; el horizonte recomendado debe leerse con esta salvedad.

**Costo si estuviera mal.** Rangos demasiado estrechos llevarían a una reserva de contingencia insuficiente. Por eso la cobertura real se muestra en la app y en el informe (entrada siguiente).

## 2026-10-31 - Aceptar una cobertura cercana al 70 % y mostrarla

**Contexto.** Con el bootstrap elegido, la cobertura empírica del P10-P90 queda entre 0,62 y 0,74 (nominal 0,80).

**Opciones.** (a) Ensanchar el abanico con un factor arbitrario hasta llegar a 0,80. (b) Calibración conformal. (c) Aceptar la cobertura real y mostrarla de forma visible.

**Decisión.** (c) para esta entrega; (b) queda como mejora futura.

**Por qué.** Un factor arbitrario ajustado sobre el mismo backtest que lo evalúa es sobreajuste. La calibración conformal es el camino correcto, pero no hubo tiempo de validarla bien. Mostrar el número real es más honesto que esconderlo: la app lo indica en Validación de modelos y el agente tiene la instrucción de mencionarlo.

**Costo si estuviera mal.** Aproximadamente 3 de cada 10 meses el costo real cae fuera del rango (en lugar de 2 de cada 10). En presupuesto, la reserva P90 − P50 cubre algo menos de lo que su nombre sugiere.

## 2026-11-01 - Horizonte confiable y umbrales

**Contexto.** El caso pide un horizonte "adecuado y justificado" y no fija uno.

**Opciones.** (a) Fijar 12 meses por costumbre. (b) Elegir con datos: el mayor horizonte en que el mejor modelo tiene MAPE ≤ umbral y la cobertura ≥ umbral, tomando el peor de los dos equipos.

**Decisión.** (b) con MAPE ≤ 15 % y cobertura ≥ 65 % (`HORIZONTE_MAX_MAPE` y `HORIZONTE_MIN_COB` en `src/config.py`). Resultado: **3 meses**. El Equipo 2 llegaría a 6 meses (MAPE 12,1 %, cobertura 0,72); el Equipo 1 se limita a 3 porque a 6 meses su mejor MAPE es 15,4 %. Se proyectan 12 meses, pero los meses 4 a 12 se marcan como "referenciales".

**Por qué.** 15 % es un error que todavía sirve para presupuestar con reserva; 65 % evita confiar en rangos que fallan uno de cada tres meses o más. Los umbrales viven en un solo lugar para que el pipeline y la app no se contradigan. Los valores por defecto de `choose_horizon` (10 % / 70 %) darían 1 mes, lo que deja la herramienta sin uso práctico para presupuestar.

**Costo si estuviera mal.** Umbrales distintos cambian el horizonte: con MAPE ≤ 10 % sería 1 mes; con ≤ 20 %, 9 meses. Por eso la tabla completa de MAPE y cobertura está visible y cualquiera puede aplicar otro criterio.

## 2026-11-01 - Ruido diario vs. mensual en presupuesto y cotizaciones

**Contexto.** El residuo de la fórmula es ≈ 1,8 % con datos diarios, pero ≈ 0,37 % (E1) y ≈ 0,31 % (E2) con promedios mensuales. El ruido diario parece independiente y se cancela al promediar (indicio de que los precios de los equipos se generaron con la fórmula más ruido).

**Opciones.** (a) Usar el ruido diario en el abanico. (b) Usar el ruido mensual en el abanico y advertir del ruido diario donde corresponde.

**Decisión.** (b). El abanico es de **costo promedio mensual**. El verificador de cotizaciones avisa que una compra puntual suma ≈ 1,8 % de ruido diario.

**Por qué.** Mezclar las dos escalas ensancharía el abanico mensual sin razón. Pero un proveedor cotiza un día concreto, así que la advertencia evita rechazar cotizaciones razonables.

**Costo si estuviera mal.** Bajo: el ruido residual es pequeño frente a la incertidumbre de las materias primas (el P10-P90 va de −5 % a +9 % del P50 ya en el mes 1).

## 2026-11-01 - Cantidades de ejemplo en el presupuesto

**Contexto.** El caso no entrega cuántos equipos se compran ni cuándo.

**Opciones.** (a) No hacer presupuesto. (b) Usar cantidades de ejemplo editables.

**Decisión.** (b): 3 fases (2023-10: 10 E1 + 5 E2; 2024-01: 15 E1 + 6 E2; 2024-04: 8 E1 + 4 E2), editables en la página Presupuesto con validación de la tabla.

**Por qué.** Muestra cómo se traduce el pronóstico a una decisión (P50 + reserva) sin inventar datos del cliente. Están rotuladas como ejemplo en el código y en la app.

**Costo si estuviera mal.** Ninguno si se lee como ejemplo; el riesgo es que alguien tome el total como un presupuesto real. La app lo rotula para evitarlo.

## 2026-11-01 - Streamlit como interfaz

**Contexto.** Se necesita contar la historia del análisis a un evaluador no técnico y alojar el agente. El candidato decidió no usar notebooks.

**Opciones.** (a) Notebooks de Jupyter. (b) Dashboard en Power BI / Tableau. (c) App web en Streamlit. (d) Front-end propio (React + API).

**Decisión.** Streamlit, 7 páginas en dos secciones (cliente: Resumen ejecutivo, Proyección de costos, Presupuesto y proveedores; análisis: Datos y trampas, Qué mueve el precio, Validación de modelos, Metodología) con el panel del agente a la derecha en todas. La lógica vive en `src/` con pruebas; la app solo la llama. Los resultados se calculan una vez por proceso (~40 s) y quedan en caché.

**Por qué.** Todo en Python, interactivo y fácil de correr en local. Permite el panel lateral del agente. Power BI no permite integrar el agente ni las simulaciones con la misma facilidad, y un front-end propio no cabía en 4 días.

**Costo si estuviera mal.** Streamlit escala mal para muchos usuarios concurrentes y su diseño es limitado. Para una herramienta interna de un área de compras es suficiente; la arquitectura AWS prevé un contenedor con escalado.

## 2026-11-01 - Agente de IA: modelo, herramientas, historial y respaldo

**Contexto.** El caso pide presentar los resultados en un agente que responda preguntas y combine el pronóstico con información externa de mercado.

**Opciones.** (a) Chat simple que recibe todo el resultado en el prompt. (b) Agente con herramientas (tool use) que consulta los resultados del modelo. (c) Framework de agentes (LangChain u otro).

**Decisión.** (b), con la API de Anthropic y un bucle de tool use propio (`src/agente/agente.py`, máximo 6 vueltas):

- **Modelo:** Claude Opus 5.5 (`claude-opus-5-5`), configurable con la variable `MODELO_AGENTE`; esfuerzo `medium`.
- **Herramientas:** `consultar_resultados` (fórmula, pronóstico, validación, calidad), `simular_escenario` (choques por materia prima), `evaluar_cotizacion` (misma lógica que la página Presupuesto) y `web_search` del lado del servidor (máximo 3 búsquedas por respuesta) para contexto de mercado.
- **Historial append-only:** se guarda una lista cruda de mensajes tal como van a la API (incluidos los bloques de herramientas) y una lista aparte para mostrar. Si un turno falla, se descarta completo y la conversación vuelve al estado anterior.
- **Respaldo ante rechazos:** se activa el respaldo del lado del servidor (`fallbacks="default"`); si aun así la respuesta es un rechazo, el panel muestra un mensaje claro y no se rompe. Los errores de la API (key inválida, límite de uso, sin conexión) se traducen a mensajes en español.
- **Sin key:** la app funciona igual y el panel muestra conversaciones de ejemplo rotuladas como ilustrativas.

**Por qué.** Con herramientas, toda cifra sale del modelo y no de la memoria del LLM (el prompt lo exige). Un bucle propio de ~100 líneas es más fácil de explicar y probar que un framework. El historial crudo evita errores de la API al reenviar bloques de herramientas y permite deshacer un turno fallido.

**Costo si estuviera mal.** **No se ha probado aún con la API real** (las pruebas usan un cliente simulado). Si el modelo o un parámetro no estuviera disponible, el panel mostraría un error controlado; se corrige con `MODELO_AGENTE` o ajustando la llamada. Pendiente del candidato: probarlo con su key y grabar ejemplos reales con `scripts/grabar_ejemplos.py`.

## 2026-11-01 - Arquitectura AWS diseñada pero no desplegada

**Contexto.** El caso pide una arquitectura cloud con diagrama; desplegar suma puntos extra pero no es obligatorio.

**Opciones.** (a) Diseñar y desplegar. (b) Solo diseñar, con una infografía y una tabla de servicios justificada.

**Decisión.** (b). Diseño en `docs/arquitectura.md` e infografía en `docs/arquitectura/` (SVG, HTML y versión PNG hecha en Canva) (ya no se muestran en la app). Servicios: EventBridge + Lambda (ingesta), S3 en tres zonas, ECS Fargate (procesamiento y reentrenamiento), Glue + Athena, App Runner + ECR (app), Claude vía Bedrock o API de Anthropic, Secrets Manager, IAM, CloudWatch + Budgets.

**Por qué.** Con 4 días, el tiempo rendía más en el análisis y la app. Desplegar implica costo, credenciales y riesgo de dejar recursos abiertos sin poder mantenerlos. El diseño es serverless o de contenedores gestionados para que el despliegue posterior sea directo.

**Costo si estuviera mal.** Se pierde el +5 % de "hacerlo en la nube". El diseño no está validado en la práctica (costos reales, permisos, tiempos de arranque).
