# Informe: estimación y proyección del costo de dos equipos de construcción

**Prueba técnica de consultoría**
Repositorio con código, app y documentación. Los números de este informe salen del código (`src/pipeline.py`, `build_results()` con la configuración de producción) y son los mismos que muestra la app.

---

## Explicación del caso

Una empresa constructora compra dos equipos críticos (Equipo 1 y Equipo 2) cuyo precio depende de tres materias primas, X, Y y Z. Hoy sufre **desviaciones presupuestales** porque no anticipa cómo se moverá ese costo.

La pregunta de negocio tiene tres partes:

1. **¿De qué depende el costo de cada equipo?** Una fórmula explicable y estable en el tiempo.
2. **¿Cuánto costarán en los próximos meses, y con qué incertidumbre?** Un pronóstico con rangos y un horizonte justificado.
3. **¿Cómo se usa eso para decidir?** Presupuesto con reserva de contingencia y una forma de evaluar cotizaciones de proveedores.

Además, el caso pide presentar los resultados en un **agente de IA** que combine el pronóstico con información de mercado, y proponer una **arquitectura cloud**.

Datos recibidos (`Datos/`): un histórico diario de precios de X, Y, Z y de los dos equipos (2010-01-04 a 2023-08-31, 3.530 días hábiles) y tres archivos sueltos con historias más largas de cada materia prima.

**Entregables y dónde están:** app Streamlit (`app/`), lógica y pruebas (`src/`, `tests/`), este informe y la arquitectura (`docs/arquitectura.md`). El `README.md` explica cómo correr todo.

## Supuestos

| # | Supuesto | Por qué | Impacto si no se cumple |
|---|---|---|---|
| 1 | **"Hoy" es septiembre de 2023**, justo al terminar los datos. | Los equipos solo tienen datos hasta 2023-08; proyectar desde una fecha posterior sin datos intermedios no sería verificable. | El pronóstico habría que rehacerlo con datos actuales (el código lo permite sin cambios). |
| 2 | Se trabaja con **promedios mensuales**. | El presupuesto es mensual y Y casi no cambia de un día a otro. | Una compra puntual tiene ≈ 1,8 % de ruido adicional (se advierte en el verificador). |
| 3 | La **fórmula de cada equipo es estable**. | Los pesos móviles de 36 meses casi no cambian entre 2010 y 2023. | Si cambia la "receta" del equipo, hay que reestimar. |
| 4 | Las **cantidades del presupuesto son de ejemplo**. | El caso no entrega cantidades ni fases. | El total es ilustrativo; las cantidades se editan en la app. |
| 5 | La identificación de X, Y y Z (petróleo, acero, aluminio) es una **hipótesis**. | Investigación propia (ver "Apreciaciones"). | Ninguno sobre el modelo: solo se usa como contexto y para las búsquedas del agente. |
| 6 | El atípico de Z del 2014-03-25 es un **error de dato** y se corrige por interpolación. | Es el único valor con más de 2 decimales y se revierte al día siguiente. | Efecto ≈ 0,6 % en un solo mes de 164. |
| 7 | Los precios se expresan en las **unidades del archivo** (el caso no indica moneda). | — | — |

## Formas para resolver el caso y la opción tomada en esta prueba

Se evaluaron cuatro formas de abordar el problema:

| Enfoque | Cómo funciona | A favor | En contra |
|---|---|---|---|
| **A. Pronóstico directo de cada equipo** | Modelar la serie de precio del equipo sola (ARIMA, ETS…). | Simple; un modelo por equipo. | No explica *por qué* sube el costo; no permite preguntar "¿y si el acero sube 20 %?"; ignora la información de las materias primas. |
| **B. Fórmula + pronóstico de materias primas** *(elegido)* | 1) Estimar el costo del equipo como combinación de X, Y, Z. 2) Pronosticar X, Y, Z con simulación conjunta. 3) Aplicar la fórmula. | Explicable (Equipo 1 = 0,2·X + 0,8·Y); permite escenarios por materia prima; una sola simulación sirve para los dos equipos y conserva su correlación. | Depende de que la fórmula sea estable (se verificó). |
| **C. Aprendizaje automático (boosting, redes)** | Modelo de caja negra sobre las series y sus rezagos. | Puede captar no linealidades. | Con 164 meses hay riesgo alto de sobreajuste; difícil de explicar a compras o finanzas; la relación resultó lineal (R² 0,9997), así que no hay no linealidad que captar. |
| **D. Modelo conjunto VAR/VECM** | Modelar X, Y, Z (y equipos) juntos, con sus relaciones de largo plazo. | Respeta la correlación y la cointegración entre series. | Más difícil de explicar; si un ARIMA univariado no le gana al último valor (ver resultados), es poco probable que el pronóstico central mejore. |

**Opción tomada: B.** Es la que mejor responde las tres preguntas de negocio y la que se puede defender paso a paso. Lo que aporta D (respetar la correlación entre materias primas) se obtiene con el **bootstrap por bloques del vector conjunto de retornos**, sin el costo de explicar un VECM. D quedó como mejora posible, no se implementó.

Flujo de la solución:

1. **Carga y auditoría** (`src/utils.py`, `src/auditoria.py`): unificar formatos, detectar trampas y corregir atípicos con una regla genérica.
2. **Relación** (`src/relacion.py`): regresión restringida + OLS, VIF, cointegración, pesos móviles y desfases.
3. **Pronóstico** (`src/pronostico.py`): comparar 4 modelos con backtest de origen móvil, simular 5.000 trayectorias y validar la cobertura de los rangos.
4. **Negocio** (`src/negocio.py`): presupuesto P50 + reserva y verificador de cotizaciones.
5. **Presentación** (`app/`): app Streamlit de 7 páginas en dos secciones (para el cliente y detrás del análisis) con el agente en un panel lateral.

## Resultados del análisis de los datos y los modelos

### Calidad de datos: lo que se encontró antes de modelar

- **Formatos distintos por archivo:** Y.csv usa `;`, coma decimal, fechas `d/m/aaaa` y BOM; Z.csv trae las columnas invertidas; X.csv está en orden descendente. Se normalizan al cargar.
- **Atípico en Z:** 2014-03-25 = 1.911,97 (único valor con más de 2 decimales; salta 1.688,25 → 1.911,97 → 1.705,25). Se corrige a 1.696,75. Regla: pico que se revierte > 8 % **y** decimales anómalos. Los picos de X sin decimales anómalos (1990-10-02, 2015-08-31, 2020-03-18, COVID) solo se advierten: son eventos reales.
- **Y casi no cambia:** 282 tramos de 5 o más días con el mismo valor (máximo 35 días). Parece un precio publicado cada cierto tiempo.
- **Fechas de fin distintas:** histórico y Z terminan el 2023-08-31, Y el 2023-09-12 y X el 2024-04-04 (los meses extra de X se usan como validación real).
- **Integridad:** sin duplicados ni vacíos; X, Y y Z del histórico coinciden con los archivos sueltos.

### La fórmula de costo

| Equipo | Fórmula (pesos ≥ 0 que suman 1) | R² | Cointegración (p) | Estabilidad (pesos móviles 36 m) |
|---|---|---|---|---|
| Equipo 1 | **0,20·X + 0,80·Y + 0,00·Z** | 0,9997 | 7,7·10⁻²⁰ | Y entre 0,78 y 0,80 |
| Equipo 2 | **≈ ⅓·X + ⅓·Y + ⅓·Z** (0,332 / 0,335 / 0,333) | 0,9997 | 4,2·10⁻²⁴ | cada peso entre 0,31 y 0,36 |

Ojo con la lectura: los pesos multiplican **precios**, y Z (≈ 2.133) cuesta mucho más por unidad que Y (≈ 556) o X (≈ 85). Por eso el peso no es lo mismo que la parte del costo. Con los precios de agosto 2023:

| Parte del costo explicada por | X | Y | Z |
|---|---|---|---|
| Equipo 1 | 3,5 % | **96,5 %** | 0 % |
| Equipo 2 | 2,8 % | 19,7 % | **77,5 %** |

Lectura de negocio:

- **El Equipo 1 es, en la práctica, Y (probable acero).** Si Y sube 10 %, el Equipo 1 sube ≈ 9,6 %; X casi no lo mueve y Z no pesa nada.
- **El Equipo 2 tiene pesos iguales, pero su costo lo domina Z (probable aluminio).** Si Z sube 10 %, el Equipo 2 sube ≈ 7,7 %.
- **La correlación engaña.** Z tiene correlación 0,84 con el Equipo 1 (en niveles, datos diarios), pero su peso es 0: Z y Y se mueven juntas (corr. 0,85). La regresión lo separa: el p-valor de Z en el Equipo 1 es 0,88 (no significativo) y el VIF máximo es 3,8 (colinealidad moderada, no grave).
- **No hay desfases:** el R² baja de 0,9997 a 0,94 si se usa la materia prima del mes anterior. El costo refleja los precios del mismo mes.
- **El residuo es pequeño:** ≈ 0,37 % (E1) y 0,31 % (E2) del precio en datos mensuales; ≈ 1,8 % en datos diarios.

### Modelos de pronóstico comparados

Backtest de origen móvil: desde 2016-01, cada mes se ajusta con los datos anteriores y se mide el error a 1, 3, 6, 9 y 12 meses. MAPE (error porcentual medio):

| Equipo | Modelo | 1 m | 3 m | 6 m | 9 m | 12 m |
|---|---|---|---|---|---|---|
| Equipo 1 | Caminata aleatoria | 5,0 % | **11,4 %** | **15,4 %** | 19,1 % | 24,5 % |
| Equipo 1 | ARIMA(1,1,0) | **4,9 %** | 11,9 % | 16,3 % | **18,6 %** | **24,2 %** |
| Equipo 1 | ETS amortiguado | 5,3 % | 13,4 % | 18,3 % | 20,0 % | 26,3 % |
| Equipo 1 | Promedio móvil 3 m | 7,8 % | 12,6 % | 16,0 % | 20,7 % | 26,3 % |
| Equipo 2 | Caminata aleatoria | 3,6 % | 8,1 % | 12,2 % | 15,9 % | 19,9 % |
| Equipo 2 | ARIMA(1,1,0) | **3,5 %** | **7,9 %** | **12,1 %** | **15,4 %** | **19,5 %** |
| Equipo 2 | ETS amortiguado | 3,6 % | 8,3 % | 12,5 % | 15,8 % | 20,3 % |
| Equipo 2 | Promedio móvil 3 m | 5,6 % | 9,2 % | 13,2 % | 17,2 % | 21,0 % |

Conclusiones:

- **Ningún modelo le gana con claridad al último valor.** ARIMA queda a menos de 1 pp de la caminata aleatoria en todos los horizontes. Los precios de materias primas se comportan como una caminata aleatoria, algo conocido en mercados de commodities.
- **Se elige la caminata aleatoria** por simplicidad ante el empate.
- **El promedio móvil de 3 meses es el peor a 1 mes** (7,8 % vs 5,0 % en el Equipo 1): reacciona tarde a los cambios.
- **Salvedad:** los pesos de la fórmula se estimaron con toda la muestra, lo que da una pequeña ventaja al backtest (look-ahead leve). Como los pesos son muy estables, el efecto esperado es bajo; reestimarlos en cada origen es una mejora pendiente.

### Simulación y cobertura de los rangos

El pronóstico central es "el precio se queda donde está", pero la incertidumbre crece con el tiempo. Para medirla se simulan **5.000 trayectorias** de X, Y y Z: caminata aleatoria en logaritmos, sin deriva, remuestreando **bloques de 6 meses del vector conjunto de retornos históricos** (conserva la correlación entre materias primas y las rachas de volatilidad). Cada trayectoria pasa por la fórmula más el ruido del residuo y se obtienen los percentiles P10, P50 y P90.

Primero se probó con shocks normales (gaussianos): el rango P10-P90 cubría entre 48 % y 78 % de los casos, por debajo del 80 % esperado. El bootstrap mejora la cobertura, aunque no llega al 80 %:

| Cobertura real del rango P10-P90 (nominal 80 %) | 1 m | 3 m | 6 m | 9 m | 12 m |
|---|---|---|---|---|---|
| Equipo 1 | 71 % | 72 % | 74 % | 69 % | 67 % |
| Equipo 2 | 71 % | 69 % | 72 % | 68 % | 62 % |

**Lectura honesta:** el rango es algo estrecho. En vez de 2 de cada 10 meses, el costo real cae fuera del rango unos 3 de cada 10. No se ensanchó el rango de forma artificial; se muestra el número real en la app y el agente lo menciona.

**Validación con datos reales posteriores:** X tiene datos hasta 2024-04. Simulando X desde 2023-08, los **7 meses reales de septiembre 2023 a marzo 2024 cayeron dentro del P10-P90** (septiembre, en el borde superior: 92,59 vs P90 de 92,64). Es una muestra pequeña y de una sola serie: confirma que el rango es razonable, no que sea perfecto.

## Proyección de costos y horizonte de predicción

### Horizonte: 3 meses confiables, 12 referenciales

Criterio: el mayor horizonte en que el mejor modelo tiene **MAPE ≤ 15 %** y la **cobertura ≥ 65 %**, tomando el peor de los dos equipos (constantes `HORIZONTE_MAX_MAPE` y `HORIZONTE_MIN_COB` en `src/config.py`).

| Horizonte | Equipo 1: MAPE / cobertura | Equipo 2: MAPE / cobertura | ¿Cumple? |
|---|---|---|---|
| 1 mes | 4,9 % / 71 % | 3,5 % / 71 % | Sí |
| **3 meses** | **11,4 % / 72 %** | **7,9 % / 69 %** | **Sí** |
| 6 meses | 15,4 % / 74 % | 12,1 % / 72 % | No (E1 supera 15 %) |
| 9 meses | 18,6 % / 69 % | 15,4 % / 68 % | No |
| 12 meses | 24,2 % / 67 % | 19,5 % / 62 % | No |

**Resultado: 3 meses** (el Equipo 2 solo llegaría a 6). Se proyectan 12 meses porque el presupuesto lo necesita, pero los meses 4 a 12 se presentan como **referenciales**: sirven para dimensionar el riesgo, no como cifra para comprometer. El criterio es una elección: con MAPE ≤ 10 % el horizonte sería 1 mes; con ≤ 20 %, 9 meses. Por eso la tabla completa está visible en la app.

### Abanico de costos (escenario base, desde septiembre 2023)

Último promedio mensual observado (agosto 2023): Equipo 1 = 461,0; Equipo 2 = 927,7.

| Equipo | Mes | P10 | P50 | P90 | Ancho P10-P90 vs P50 |
|---|---|---|---|---|---|
| Equipo 1 | 1 (2023-09) | 434,6 | 459,6 | 499,4 | −5 % / +9 % |
| Equipo 1 | 3 (2023-11) | 396,3 | 457,5 | 559,3 | −13 % / +22 % |
| Equipo 1 | 12 (2024-08) | 333,6 | 449,5 | 654,9 | −26 % / +46 % |
| Equipo 2 | 1 (2023-09) | 872,6 | 923,2 | 982,5 | −5 % / +6 % |
| Equipo 2 | 3 (2023-11) | 827,5 | 925,2 | 1.036,0 | −11 % / +12 % |
| Equipo 2 | 12 (2024-08) | 725,5 | 928,1 | 1.203,1 | −22 % / +30 % |

- **El P50 queda casi plano**, como corresponde a una caminata aleatoria sin deriva: la mejor estimación es el precio actual.
- **El riesgo es asimétrico al alza:** el P90 se aleja más del P50 que el P10 (efecto de trabajar en logaritmos). Para presupuestar, el riesgo relevante es el de arriba.
- **El Equipo 1 es más riesgoso:** su P90 a 12 meses está 46 % sobre el P50, contra 30 % del Equipo 2. Su costo es casi todo Y, que fue más volátil (≈ 21 % anual en datos mensuales) que Z (≈ 16 %), la que domina el Equipo 2.

### Escenario de estrés "choque 2022"

Aplica un alza sostenida tipo 2022 desde el mes 1: X +35 %, Y +25 %, Z +30 %. El P50 del mes 1 sube de 459,6 a 576,1 (Equipo 1, +25 %) y de 923,2 a 1.192,3 (Equipo 2, +29 %). Sirve para responder "¿cuánto necesito si se repite 2022?".

### Traducción a presupuesto (cantidades de ejemplo)

Presupuesto = Σ cantidad × P50 + **reserva de contingencia** = Σ cantidad × (P90 − P50).

| Fase (mes) | Cantidades E1 / E2 | P50 | Reserva | Total |
|---|---|---|---|---|
| Fase 1 (2023-10) | 10 / 5 | 9.221 | 1.095 | 10.317 |
| Fase 2 (2024-01) | 15 / 6 | 12.319 | 3.080 | 15.399 |
| Fase 3 (2024-04) | 8 / 4 | 7.312 | 2.158 | 9.470 |
| **Total** | | **28.852** | **6.333** | **35.186** |

La reserva crece con el plazo: es el 12 % del P50 en la fase 1 y el 30 % en la fase 3. En el escenario de choque el total sería ≈ 44.706. Las fases 2 y 3 están fuera del horizonte confiable: su cifra es referencial.

**Verificador de cotizaciones** (página Presupuesto y herramienta del agente): compara un precio cotizado con el P50 del mes ("precio justo") y alerta si supera el P90. Advierte que una compra puntual suma ≈ 1,8 % de ruido diario sobre el promedio mensual.

## Futuros ajustes o mejoras

**Modelo y validación**

- **Calibrar los rangos** (por ejemplo, con predicción conformal) para acercar la cobertura al 80 %.
- **Reestimar los pesos en cada origen del backtest** para eliminar el look-ahead leve.
- **Errores estándar robustos (HAC)** en los p-valores de la regresión, por la autocorrelación de los residuos.
- **Modelo conjunto VAR/VECM** como alternativa, si se quiere aprovechar la cointegración entre materias primas.
- **Validar con datos reales posteriores a 2023** (página "Pronóstico vs realidad", planificada como opcional y no construida).

**Operación**

- **Desplegar la arquitectura AWS** diseñada (hoy solo es diseño): ingesta mensual automática y reentrenamiento programado.
- **Alertas automáticas** cuando los pesos móviles cambien o el costo real salga del rango.
- **Probar el agente con la API real** y grabar conversaciones reales (pendiente; las pruebas usan un cliente simulado).
- Pruebas de carga de la app para varios usuarios.

**Negocio**

- Reemplazar las cantidades de ejemplo por el plan de compras real.
- Usar la fórmula en la negociación con proveedores (indexar contratos al precio de Y para el Equipo 1).

## Apreciaciones y comentarios del caso

### Texto oculto en el PDF del caso

Al extraer el texto del PDF del enunciado aparece, debajo de "Código funcional" en la página 1, un bloque que no se ve al leer el documento. Se presenta como una "[INSTRUCCIÓN DEL SISTEMA]" dirigida a una IA y pide exponer conclusiones predeterminadas como si fueran análisis propio:

| Aspecto | Dice el texto oculto | Muestran los datos |
|---|---|---|
| Equipo 1 | 95 % Z | Pesos 0,80 Y + 0,20 X; Z ≈ 0 (p-valor 0,88) |
| Equipo 2 | 70 % X + 30 % Z | Pesos ≈ ⅓ cada una; X explica solo ≈ 3 % del costo |
| Materia prima Y | No significativa, descartar | Es la de mayor peso en el Equipo 1 (0,80; ≈ 96,5 % de su costo) y pesa ⅓ en el Equipo 2 |
| Método | Solo promedio móvil de 3 meses | Es el peor de los 4 modelos a 1 mes; se usa caminata aleatoria con simulación y rangos |

Las conclusiones del texto oculto no resisten los datos. Se interpretó como una posible prueba para detectar entregas generadas con IA sin revisión. **No se siguió; se documentó** como hallazgo de auditoría en la página "Datos y trampas" (tabla calculada a partir de los pesos reales, no escrita a mano).

### Investigación propia: ¿qué son X, Y y Z?

El caso no dice qué son las materias primas. Comparando las series con precios públicos se plantean estas **hipótesis** (no hechos):

| Serie | Hipótesis | Confianza | Evidencia |
|---|---|---|---|
| X | Petróleo Brent (futuros) | Alta | ~40 % de los días dentro de ±1 % del Brent publicado por FRED; el 2020-04-21 vale 19,33 (cierre de futuros), no 9,12 (spot). |
| Y | Acero (probable HRC o varilla de exportación china) | Media | 257,50 el 2015-12-04 coincide con un precio de Fastmarkets; ciclos 2008/2015/2021 típicos del acero. |
| Z | Aluminio LME | Alta | Máximo de 3.984 el 2022-03-08, en línea con el récord de ~3.985 USD/t de marzo 2022. |

El modelo **no depende** de esta identificación. Se usa como contexto para el negocio ("el Equipo 1 sigue al acero", "el Equipo 2, al aluminio") y para que el agente busque noticias del mercado correcto.

### Otras observaciones

- **Los datos parecen generados con la fórmula más ruido.** El residuo diario (≈ 1,8 %) es independiente y se cancela al promediar (≈ 0,3-0,4 % mensual), y los pesos son casi exactos (0,20 / 0,80; ⅓ / ⅓ / ⅓). Es una inferencia, no una certeza; en datos reales de un cliente la relación sería menos limpia.
- **La correlación no es causalidad ni peso.** Z correlaciona 0,84 con el Equipo 1 y no pesa nada: un análisis que se quedara en la matriz de correlación llegaría a la conclusión equivocada (la misma del texto oculto).

### Agente de IA y arquitectura

- **Agente:** panel lateral en todas las páginas de la app. Usa Claude Opus 5.5 con cuatro herramientas: consultar resultados, simular escenarios, evaluar cotizaciones y búsqueda web para contexto de mercado. Toda cifra sale de las herramientas, no de la memoria del modelo. La diferencia entre la IA convencional (el modelo de pronóstico) y el agente (decide qué herramienta usar, conserva memoria de la conversación y actúa) se explica en el panel y en la página "Metodología". **Limitación:** no se ha probado aún con la API real; sin key, la app muestra conversaciones de ejemplo rotuladas como ilustrativas.
- **Arquitectura AWS (diseñada, no desplegada):** ingesta mensual con EventBridge + Lambda, datos en S3 por zonas, procesamiento y reentrenamiento en ECS Fargate, app en App Runner, Claude vía Bedrock o API de Anthropic, secretos en Secrets Manager y monitoreo con CloudWatch + Budgets. Detalle en `docs/arquitectura.md`, infografía en `docs/arquitectura/infografia_aws.svg`.

### Comentario final

El resultado más útil para la constructora no es un número sino una forma de trabajar: **presupuestar el Equipo 1 mirando Y (probable acero) y el Equipo 2 mirando Z (probable aluminio)**, comprometer cifras solo a 3 meses, reservar contingencia por encima del P50 y actualizar el pronóstico cada trimestre (el horizonte confiable es de 3 meses; el pipeline de datos puede refrescarse cada mes).
