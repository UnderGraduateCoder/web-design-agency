# CONTRATO DE AUTORIZACIÓN PARA AUDITORÍA DE SEGURIDAD

---

## Datos del Contrato

| Campo | Valor |
|---|---|
| **Número de contrato** | ASC-[YYYY]-[NNN] |
| **Fecha de emisión** | [DD/MM/YYYY] |
| **Versión del documento** | 1.0 |

**Partes del contrato:**

**Prestador del servicio (Auditor):**
- Empresa: Cifra
- Contacto: adrianarconroyo@gmail.com
- En adelante denominado "el Auditor"

**Cliente:**
- Nombre del representante: [NOMBRE COMPLETO]
- Cargo: [CARGO EN LA EMPRESA]
- Empresa: [NOMBRE DE LA EMPRESA]
- CIF/NIF: [CIF/NIF DE LA EMPRESA]
- Dirección: [DIRECCIÓN COMPLETA]
- Email: [EMAIL DE CONTACTO]
- Teléfono: [TELÉFONO DE CONTACTO]
- En adelante denominado "el Cliente"

---

## 1. Objeto del Contrato

El presente contrato autoriza expresamente a Cifra a realizar una auditoría de seguridad sobre los sistemas y repositorios de código indicados en la sección "Alcance" de este documento. El Cliente confirma que tiene los derechos y la autoridad legal para autorizar esta auditoría sobre los sistemas descritos.

---

## 2. Alcance (Scope)

### 2.1 Sistemas y repositorios autorizados para el análisis

El Auditor queda expresamente autorizado para analizar únicamente los siguientes sistemas:

| # | Sistema / Repositorio | URL o ruta | Descripción |
|---|---|---|---|
| 1 | [Nombre del repo] | [https://github.com/...] | [Descripción breve] |
| 2 | [Nombre del repo] | [URL o ruta local] | |
| 3 | | | |

### 2.2 Sistemas explícitamente EXCLUIDOS del análisis

Los siguientes sistemas quedan **explícitamente fuera del alcance** de esta auditoría y no deben ser analizados en ninguna circunstancia:

- [Sistema o URL excluido 1]
- [Sistema o URL excluido 2]
- Cualquier sistema de terceros no listado en la sección 2.1

### 2.3 Metodología autorizada

La auditoría se limitará estrictamente a las siguientes técnicas:

✅ **Permitido:**
- Análisis estático de código fuente (revisión sin ejecución)
- Lectura de archivos de configuración y dependencias
- Análisis mediante inteligencia artificial (Anthropic Claude)
- Revisión de patrones de autenticación, manejo de datos y validación de entradas

❌ **No permitido:**
- Pruebas de penetración activa (pentesting) sobre sistemas en producción
- Ejecución de exploits o payloads contra el sistema
- Acceso a bases de datos de producción
- Análisis de redes o infraestructura de hosting
- Ingeniería social sobre empleados del Cliente

---

## 3. Duración

| Campo | Fecha |
|---|---|
| **Fecha de inicio** | [DD/MM/YYYY] |
| **Fecha de finalización** | [DD/MM/YYYY] |
| **Entrega del informe** | Máximo [N] días hábiles tras el inicio |

Esta autorización es válida únicamente durante el período indicado. Para auditorías adicionales o renovaciones será necesario un nuevo contrato firmado.

**Cláusula de renovación:** Las partes podrán acordar por escrito la renovación o ampliación del alcance, lo que requerirá la firma de un anexo o un nuevo contrato.

---

## 4. Contacto de Emergencia

En caso de que el Auditor identifique una vulnerabilidad crítica que requiera atención inmediata, el Cliente designa el siguiente contacto técnico de emergencia:

| Campo | Valor |
|---|---|
| **Nombre** | [NOMBRE COMPLETO DEL RESPONSABLE TÉCNICO] |
| **Cargo** | [CTO / Responsable de IT / etc.] |
| **Teléfono móvil (24h)** | [+34 XXX XXX XXX] |
| **Email directo** | [email@empresa.com] |
| **Tiempo máximo de respuesta** | [2 horas / 4 horas] desde la notificación |

El Auditor se compromete a notificar al contacto de emergencia de forma inmediata si detecta cualquier hallazgo de severidad Alta (HIGH) que represente un riesgo activo para el sistema en producción.

---

## 5. Limitación de Responsabilidad

### 5.1 Límites de responsabilidad del Auditor

Cifra no asumirá responsabilidad alguna por:

- Vulnerabilidades preexistentes en el sistema antes de la fecha de inicio indicada en la sección 3
- Vulnerabilidades introducidas en el código después de la fecha de finalización del análisis
- Decisiones de negocio o técnicas tomadas por el Cliente en base a los hallazgos del informe
- Daños derivados de ataques de terceros que se produzcan durante o después del período de la auditoría
- Vulnerabilidades en sistemas explícitamente excluidos del alcance (sección 2.2)

### 5.2 Límite económico de responsabilidad

En ningún caso la responsabilidad total de Cifra derivada de este contrato superará el importe total facturado por el servicio objeto del presente contrato.

### 5.3 Limitaciones del análisis

El Cliente comprende y acepta que:
- El análisis está basado en el estado del código en el momento del análisis y puede no detectar el 100% de las vulnerabilidades existentes
- La ausencia de hallazgos en el informe no garantiza que el sistema sea completamente seguro
- El análisis se limita al código fuente accesible y no incluye análisis de infraestructura, redes ni entornos de ejecución

---

## 6. Confidencialidad y Divulgación Coordinada

### 6.1 Tratamiento de los hallazgos

Todos los hallazgos de seguridad identificados durante esta auditoría son información estrictamente confidencial. El Auditor se compromete a:

- No publicar, divulgar ni compartir ningún hallazgo fuera de este engagement sin el consentimiento previo y por escrito del Cliente
- Seguir las prácticas de divulgación coordinada de Anthropic
- Entregar los hallazgos únicamente al representante del Cliente identificado en este contrato
- Destruir o devolver al Cliente toda la información sensible al finalizar el engagement

### 6.2 Obligaciones de confidencialidad del Cliente

El Cliente se compromete a no publicar el informe completo en canales públicos sin anonimizar los detalles técnicos específicos que podrían facilitar la explotación de vulnerabilidades no corregidas.

### 6.3 Retención de datos

Cifra conservará una copia del informe final durante un máximo de [12 meses] por razones de documentación interna, tras lo cual será eliminado de forma segura.

---

## 7. Protección de Datos (RGPD)

Conforme al Reglamento General de Protección de Datos (RGPD) y la Ley Orgánica 3/2018 de Protección de Datos Personales (LOPDGDD):

- Cifra tratará los datos personales del Cliente únicamente para la prestación del servicio descrito en este contrato
- Los datos no serán cedidos a terceros salvo obligación legal
- El Cliente tiene derecho a acceder, rectificar, suprimir y portar sus datos

---

## 8. Legislación Aplicable y Jurisdicción

Este contrato se rige por la legislación española. Las partes acuerdan someterse, para la resolución de cualquier controversia derivada de este contrato, a los juzgados y tribunales de [CIUDAD], con renuncia expresa a cualquier otro fuero que pudiera corresponderles.

---

## 9. Firmas

Al firmar este documento, ambas partes declaran haber leído, comprendido y aceptado todas las condiciones establecidas en el presente contrato.

---

**Por el Cliente:**

Nombre: _______________________________________________

Cargo: ________________________________________________

Empresa: ______________________________________________

Firma: ________________________________________________

Fecha: ________________________________________________

---

**Por Cifra (el Auditor):**

Nombre: Adrián Arcón Royo

Cargo: Responsable de Auditorías de Seguridad

Firma: ________________________________________________

Fecha: ________________________________________________

---

*Una vez firmado por ambas partes, el Cliente debe enviar este documento como PDF a adrianarconroyo@gmail.com y guardarlo en `brand_assets/{client_slug}/authorization_signed.pdf` antes de iniciar el análisis.*
