# INFORME DE AUDITORÍA DE SEGURIDAD

---

## Encabezado

| Campo | Valor |
|---|---|
| **Cliente** | [NOMBRE DEL CLIENTE] |
| **Empresa** | [NOMBRE DE LA EMPRESA] |
| **Sistema auditado** | [URL o ruta del repositorio] |
| **Fecha del informe** | [YYYY-MM-DD] |
| **Auditor** | Cifra |
| **Referencia del contrato** | [NÚMERO DE CONTRATO / brand_assets/{slug}/authorization_signed.pdf] |
| **Modelo de análisis** | Claude Sonnet (Anthropic) — claude-code-security-review framework |

---

## 1. Resumen Ejecutivo

[2–3 párrafos escritos a mano por el auditor que resuman:]
- El propósito y alcance de la auditoría
- La postura de seguridad general del sistema analizado
- El número total de hallazgos por severidad
- La recomendación principal de acción inmediata (si aplica)

**Ejemplo:**
> Se ha realizado una auditoría de seguridad del repositorio `[nombre del repo]` en nombre de `[nombre del cliente]`. El análisis ha examinado `[N]` archivos de código fuente, incluyendo lógica de autenticación, acceso a base de datos, manejo de entradas de usuario y exposición de APIs.
>
> Se han identificado **[N] hallazgos en total**: [N] de severidad Alta, [N] de severidad Media y [N] de severidad Baja. Los hallazgos de severidad Alta requieren atención inmediata antes de cualquier despliegue en producción.
>
> En general, el sistema presenta [descripción honesta: p.ej. "una base de código bien estructurada con vulnerabilidades puntuales en la capa de acceso a datos" o "múltiples vectores de ataque en la lógica de autenticación"].

**Resumen de hallazgos:**

| Severidad | Español | Total |
|---|---|---|
| HIGH | Alta | [N] |
| MEDIUM | Media | [N] |
| LOW | Baja | [N] |
| **TOTAL** | | **[N]** |

---

## 2. Hallazgos por Severidad

### 2.1 Alta Severidad (HIGH)

> Vulnerabilidades directamente explotables: ejecución remota de código, robo de datos, evasión de autenticación. Deben corregirse antes del próximo despliegue.

| ID | Archivo afectado | Línea | Categoría | Descripción | Escenario de explotación | Recomendación | Confianza |
|---|---|---|---|---|---|---|---|
| H-01 | `[ruta/al/archivo.py]` | [42] | [Ej: SQL Injection] | [Descripción concisa de la vulnerabilidad] | [Cómo un atacante podría explotarla] | [Qué cambiar y cómo] | [0.XX] |
| H-02 | | | | | | | |

---

### 2.2 Media Severidad (MEDIUM)

> Vulnerabilidades con impacto significativo que requieren condiciones específicas para ser explotadas. Corregir dentro del sprint actual.

| ID | Archivo afectado | Línea | Categoría | Descripción | Escenario de explotación | Recomendación | Confianza |
|---|---|---|---|---|---|---|---|
| M-01 | `[ruta/al/archivo.js]` | [18] | [Ej: XSS Almacenado] | [Descripción] | [Escenario] | [Recomendación] | [0.XX] |
| M-02 | | | | | | | |

---

### 2.3 Baja Severidad (LOW)

> Mejoras de defensa en profundidad o vulnerabilidades de bajo impacto. Planificar en el backlog.

| ID | Archivo afectado | Línea | Categoría | Descripción | Recomendación |
|---|---|---|---|---|---|
| L-01 | `[ruta/al/archivo]` | [N/A] | [Ej: Configuración] | [Descripción] | [Recomendación] |
| L-02 | | | | | |

---

## 3. Plan de Remediación

Acciones priorizadas para corregir los hallazgos identificados:

### Prioridad 1 — Inmediata (antes del próximo despliegue)

| Hallazgo | Acción requerida | Esfuerzo estimado | Responsable |
|---|---|---|---|
| H-01 | [Descripción de la acción correctiva] | [X horas / X días] | [Dev / Equipo] |
| H-02 | | | |

### Prioridad 2 — Sprint actual

| Hallazgo | Acción requerida | Esfuerzo estimado | Responsable |
|---|---|---|---|
| M-01 | [Descripción] | [X horas] | |
| M-02 | | | |

### Prioridad 3 — Backlog

| Hallazgo | Acción requerida | Esfuerzo estimado |
|---|---|---|
| L-01 | [Descripción] | [X horas] |

---

## 4. Metodología

Esta auditoría ha sido realizada mediante el framework oficial de revisión de seguridad de Anthropic (`claude-code-security-review`), basado en análisis estático de código con inteligencia artificial.

**Proceso:**
1. **Recopilación de contexto**: Se recopilaron todos los archivos de código fuente del repositorio objetivo (Python, JavaScript, TypeScript, SQL, configuraciones YAML, etc.)
2. **Análisis de patrones**: Se identificaron los frameworks de seguridad existentes, patrones de validación de entrada, y prácticas de manejo de datos sensibles.
3. **Evaluación de vulnerabilidades**: Se analizó el flujo de datos desde las entradas del usuario hasta las operaciones críticas, identificando puntos de inyección y vectores de ataque.
4. **Filtrado de falsos positivos**: Solo se reportan hallazgos con un nivel de confianza ≥ 0.80 y un camino de explotación concreto.

**Categorías examinadas:**
- Inyección (SQL, comandos, plantillas, NoSQL)
- Autenticación y autorización
- Gestión de secretos y criptografía
- Ejecución remota de código
- Exposición de datos sensibles y PII

**Exclusiones del análisis** (por diseño del framework):
- Vulnerabilidades de denegación de servicio (DoS)
- Librerías de terceros desactualizadas
- Limitación de velocidad de peticiones (rate limiting)
- Secretos almacenados en disco

---

## 5. Niveles de Servicio y Precios

### Opción A — Corrección Única

**Servicio:** Corrección puntual de los hallazgos identificados en esta auditoría.

| Severidad | Precio por hallazgo | Descripción |
|---|---|---|
| Alta (HIGH) | [€XXX – €XXX] | Corrección urgente con entrega en 48–72h |
| Media (MEDIUM) | [€XXX – €XXX] | Corrección con entrega en 5–7 días hábiles |
| Baja (LOW) | [€XX – €XX] | Corrección con entrega en el siguiente sprint |

**Precio estimado para este informe:** [€XXXX]
*(basado en [N] hallazgos Alta × €XXX + [N] hallazgos Media × €XXX + [N] hallazgos Baja × €XX)*

Incluye:
- Implementación de las correcciones en el repositorio del cliente
- Pull request documentado con explicación de cada cambio
- Re-escaneo de verificación tras las correcciones

---

### Opción B — Mantenimiento de Seguridad Mensual

**Servicio:** Auditorías de seguridad continuas sobre cada nuevo código añadido al repositorio.

| Plan | Precio mensual | Incluye |
|---|---|---|
| Básico | [€XXX/mes] | 1 auditoría mensual completa + informe en español |
| Estándar | [€XXX/mes] | Auditoría por cada pull request + correcciones de severidad Media/Baja incluidas |
| Premium | [€XXXX/mes] | Monitorización continua + corrección de todos los hallazgos + revisión de arquitectura trimestral |

**Recomendación para este cliente:** [Opción X — justificación breve basada en el volumen de código y la frecuencia de despliegues]

---

## 6. Aviso Legal

Este informe y todos sus contenidos son **estrictamente confidenciales**. Están destinados exclusivamente al cliente identificado en el encabezado de este documento, en el marco del contrato de autorización firmado el [fecha de firma del contrato].

**Divulgación coordinada:** De conformidad con las prácticas de divulgación coordinada de Anthropic, los hallazgos contenidos en este informe no serán publicados, compartidos con terceros, ni divulgados fuera de este engagement sin el consentimiento previo y por escrito del cliente.

Cifra no es responsable de vulnerabilidades preexistentes en el sistema antes de la fecha de la auditoría, ni de vulnerabilidades introducidas después de la fecha de cierre del análisis.

---

*Informe generado por Cifra · Tecnología AI: Anthropic Claude · Framework: claude-code-security-review*
