# BiwengerPagaBot

Bot de Telegram para consultar y analizar una liga de Biwenger, con información de mercado, jugadores, jornadas, resultados y alineaciones.

> **Rama documentada:** `alineaciones-mejoras`

---

## 1. Objetivo del proyecto

BiwengerPagaBot conecta Telegram con Biwenger para consultar información de una liga de fantasy y presentarla de forma cómoda mediante botones, mensajes e imágenes.

El proyecto utiliza dos fuentes principales de datos:

1. **API privada de Biwenger**

   * Autenticación mediante usuario y contraseña.
   * Ligas.
   * Usuarios.
   * Plantillas.
   * Mercado.
   * Historial de movimientos.
   * Propietarios.

2. **API pública de Biwenger**

   * Jugadores.
   * Información de jugadores.
   * Jornadas.
   * Partidos.
   * Resultados.
   * Reports de jugadores.
   * Puntuaciones.
   * Información de alineaciones.

La interfaz de usuario se realiza mediante `python-telegram-bot`.

---

# 2. Arquitectura actual

La arquitectura real de la aplicación es aproximadamente:

```text
                         TELEGRAM
                            │
                            ▼
                         bot.py
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
          Mercado       Jornadas       Jugadores
              │             │              │
              └─────────────┼──────────────┘
                            ▼
                       biwenger.py
                            │
                  ┌─────────┴─────────┐
                  ▼                   ▼
          API privada            API pública
          Biwenger               Biwenger
                  │                   │
                  ▼                   ▼
          Liga / usuarios       Jugadores / rounds
          mercado / board       partidos / reports
          plantillas
```

Existe además una segunda implementación de cliente:

```text
player_cache.py
       │
       ▼
biwenger_client.py
       │
       ▼
API de Biwenger
```

Esto es actualmente una duplicación arquitectónica que conviene solucionar.

---

# 3. Archivos del proyecto

Actualmente la rama contiene:

```text
.gitignore
README.txt
biwenger.py
biwenger_client.py
bot.py
config.py
lineup_image.py
partido_alineaciones.py
player_cache.py
requirements.txt
test.py
test_alineaciones.py
test_client.py
```

---

# 4. `bot.py`

Es la capa principal de Telegram.

Su responsabilidad es:

* recibir callbacks;
* mostrar menús;
* gestionar la liga seleccionada;
* solicitar información a `biwenger.py`;
* transformar los datos en mensajes;
* crear botones;
* gestionar paginación;
* mostrar fichas;
* mostrar jornadas;
* mostrar mercados;
* enviar imágenes de alineaciones.

No debería contener la lógica de acceso a la API de Biwenger.

## Menú principal de una liga

Una vez seleccionada una liga aparecen:

* Informe
* Mercado
* Jornadas
* Cambiar liga

La liga seleccionada se guarda en:

```text
context.user_data["liga"]
```

y su nombre en:

```text
context.user_data["liga_nombre"]
```

---

# 5. Selección de liga

El bot obtiene las ligas mediante:

```text
obtener_ligas()
```

Después crea un botón por liga.

El callback tiene la forma:

```text
liga:<liga_id>
```

La selección queda asociada al usuario de Telegram.

---

# 6. Sistema de mercado

El menú de mercado actualmente tiene cuatro opciones:

```text
Mercado completo
Mercado de hoy
Mercado 24h
Mercado por miembro
```

El código de `bot.py` gestiona los diferentes menús y filtros. También existe paginación para las listas grandes.

---

# 7. Mercado completo

El mercado completo utiliza el historial de movimientos de Biwenger.

El cliente recorre las páginas del endpoint `/board` utilizando fechas para retroceder en el historial.

Los eventos se deduplican mediante:

```text
date
type
title
```

y posteriormente se ordenan de más reciente a más antiguo.

El resultado se transforma en operaciones:

* comprador;
* vendedor;
* jugador;
* importe;
* fecha;
* tipo de evento.

---

# 8. Mercado de hoy

El mercado de hoy consulta:

```text
/market
```

y clasifica los jugadores en:

* jugadores puestos por el sistema;
* jugadores puestos por otros managers;
* jugadores propios.

También calcula:

* precio de venta;
* precio de compra conocido;
* valor actual;
* puntos;
* posición;
* ofertas;
* número de ofertas;
* mejor oferta.

Los jugadores pueden filtrarse por:

```text
DEL
MC
DF
PT
TODAS
```

También existe la posibilidad de mostrar u ocultar jugadores y paginarlos.

---

# 9. Mercado por miembro

Permite seleccionar un manager de la liga.

Después muestra sus movimientos agrupados por día.

La información se obtiene mediante:

```text
obtener_mercado_miembro_datos()
```

y puede navegarse por los diferentes días.

---

# 10. Jugadores

La API pública proporciona el mapa completo de jugadores.

El proyecto actualmente carga aproximadamente cientos de jugadores y los indexa por ID.

El mapa permite transformar:

```text
player_id
```

en:

```text
nombre
equipo
posición
precio
puntos
```

---

# 11. Caché de jugadores

Existen dos sistemas relacionados con jugadores.

## Caché de `biwenger.py`

`biwenger.py` mantiene un caché en memoria:

```text
_PLAYERS_CACHE
_PLAYERS_CACHE_TIME
PLAYERS_CACHE_TTL = 3600
```

Por tanto, mientras el proceso siga vivo, los jugadores se reutilizan durante aproximadamente una hora.

## `player_cache.py`

También existe un sistema separado que guarda jugadores en:

```text
/app/players.json
```

Esto introduce actualmente una duplicación de mecanismos.

Además, `config.py` define:

```text
data/players.json
data/market.json
```

pero `player_cache.py` no utiliza esas rutas.

Esto debe unificarse.

---

# 12. Ficha de jugador

La ficha de jugador se construye mediante:

```text
obtener_ficha_jugador(player_id)
```

Actualmente incluye:

* nombre;
* equipo;
* posición;
* valor actual;
* propietario;
* puntos totales;
* puntos de la última jornada;
* media de puntos.

El formato actual es:

```text
⚽ Jugador [EQUIPO] (POSICIÓN)

━━━━━━━━━━━━━━━━━━━━

👤 Nombre
🏟️ Equipo
📍 Posición
💰 Valor actual
👤 Propietario
⭐ Puntos totales
📅 Puntos última jornada
📊 Media de puntos
```

---

# 13. Propietarios

El propietario real se obtiene a partir de las plantillas de los managers de la liga.

El proceso es:

```text
liga
  ↓
standings
  ↓
usuarios
  ↓
/user/{user_id}
  ↓
players
  ↓
player_id -> propietario
```

Se construye un mapa:

```text
player_id -> nombre propietario
```

Este mapa se almacena en una caché interna.

Esto permite mostrar el propietario real aunque el objeto público del jugador no contenga directamente esa información.

---

# 14. Jornadas

El proyecto dispone de dos mecanismos.

## Jornada actual

Se utiliza:

```text
GET /rounds/la-liga
```

y se interpreta la respuesta como la jornada actual.

## Todas las jornadas

Se recorren IDs consecutivos empezando actualmente en:

```text
4899
```

hasta encontrar jornadas o llegar al límite configurado.

Las jornadas pueden tener IDs diferentes aunque compartan el mismo `short`.

Ejemplo:

```text
4899 -> J1
4900 -> J2
4901 -> J3
...
4937 -> J1 aplazada
```

Por eso el ID de Biwenger y el número de jornada no deben confundirse.

---

# 15. Problema actual de la jornada

Esta es una de las zonas que necesita especial atención.

El código tiene actualmente:

```text
obtener_jornada_actual()
```

y también:

```text
obtener_jornadas()
```

La primera consulta el endpoint general de rounds.

La segunda recorre IDs concretos.

El problema detectado durante las pruebas es que el endpoint consultado como "jornada actual" puede devolver una jornada que no coincide con la jornada que nosotros conceptualmente consideramos actual.

Por tanto, para los cálculos de estadísticas debemos definir claramente qué significa:

```text
jornada actual
```

y no asumir que:

```text
GET /rounds/la-liga
```

siempre proporciona la jornada que necesitamos.

---

# 16. Puntos de última jornada

La lógica actual intenta hacer:

```text
Jornada actual = Jn

Jornada anterior = J(n-1)

Buscar player_id
    ↓
games
    ↓
home / away
    ↓
reports
    ↓
player.id
    ↓
report.points
```

Si no existe un report del jugador, devuelve:

```text
0
```

Actualmente la función utilizada es:

```text
_obtener_puntos_jornada()
```

y la búsqueda de la jornada anterior:

```text
_obtener_jornada_anterior()
```

---

# 17. Media de puntos

La lógica actual es:

```text
puntos totales / número de jornada actual
```

Ejemplo:

```text
J3
15 puntos totales

15 / 3 = 5.00
```

La función responsable es:

```text
_extraer_media_puntos()
```

Esto es diferente de calcular una media basada únicamente en jornadas disputadas.

Por tanto, hay que mantener claro que actualmente la definición del proyecto es:

```text
media = puntos_totales / jornada_actual
```

---

# 18. Partidos

Cada jornada contiene:

```text
games
```

Cada partido puede contener:

```text
home
away
status
date
```

El helper:

```text
_resultado_partido()
```

admite varias estructuras posibles para el marcador.

Actualmente soporta:

```text
score.home
score.away
```

y también la estructura real observada:

```text
home.score
away.score
```

También intenta detectar:

```text
goals
homeScore
awayScore
```

---

# 19. Información de partidos

Las jornadas muestran:

* fecha;
* hora;
* equipo local;
* equipo visitante;
* marcador;
* estado;
* partido pendiente;
* partido en directo;
* partido finalizado.

Los estados se traducen a indicadores visuales como:

```text
✅ Finalizado
🔴 En directo
⏳ Pendiente
```

---

# 20. Alineaciones

La rama actual incluye una funcionalidad específica para alineaciones.

Está separada principalmente en:

```text
lineup_image.py
partido_alineaciones.py
```

Esto es una buena separación respecto a `bot.py`.

---

# 21. Alineación posible vs inicial

El sistema distingue entre:

```text
11 POSIBLE
```

y:

```text
11 INICIAL
```

Antes del partido utiliza los datos disponibles en:

```text
reports
```

Cuando el partido está confirmado, intenta utilizar estructuras explícitas como:

```text
initialLineup
initialLineups
lineup
lineups
starters
startingXI
```

También contempla:

```text
initialLineups = True
```

como indicador de confirmación.

---

# 22. Imágenes de alineaciones

`lineup_image.py` genera imágenes PNG mediante Pillow.

Las imágenes incluyen:

* nombre del equipo;
* rival;
* campo;
* jugadores;
* posición;
* puntos cuando la alineación está confirmada;
* indicación de alineación probable/confirmada.

El módulo también busca fuentes de letra disponibles en el sistema.

---

# 23. `partido_alineaciones.py`

Este módulo actúa como capa específica para la ficha de partido.

Permite:

* construir texto de alineaciones;
* generar imagen del local;
* generar imagen del visitante;
* generar una imagen combinada.

Utiliza las funciones de `lineup_image.py` en lugar de duplicar la lógica.

---

# 24. Informe económico

El proyecto tiene una base importante para el informe económico.

Se obtiene:

```text
standings
```

y:

```text
historial completo del mercado
```

Después se calculan:

```text
compras
ventas
número de compras
número de ventas
valor de equipo
saldo actual
puja máxima
```

El saldo se calcula actualmente como:

```text
20.000.000
+ ventas
- compras
```

La puja máxima se calcula como:

```text
saldo + valor_equipo / 4
```

---

# 25. Limitación del informe económico

Aunque la lógica existe en `biwenger.py`, la arquitectura todavía no está completamente limpia.

Hay que distinguir entre:

* datos reales actuales de Biwenger;
* datos reconstruidos mediante historial;
* datos derivados;
* datos que pueden faltar por movimientos antiguos.

Especialmente importante es el cálculo de saldo y precio de adquisición.

No debemos asumir que el historial disponible siempre contiene toda la información necesaria para reconstruir perfectamente el patrimonio histórico.

---

# 26. `biwenger.py`

Es actualmente el módulo más importante del proyecto.

Contiene:

* cliente de Biwenger;
* autenticación;
* contexto de liga;
* jugadores;
* propietarios;
* mercado;
* historial;
* jornadas;
* partidos;
* puntos;
* fichas;
* informes;
* cálculos económicos;
* formateo de datos.

Actualmente concentra demasiadas responsabilidades.

Es funcional, pero es el principal candidato a refactorización futura.

---

# 27. `biwenger_client.py`

Es una segunda implementación del cliente de Biwenger.

Incluye:

* login;
* account;
* leagues;
* búsqueda de usuario de liga;
* contexto;
* league;
* board;
* historial;
* plantillas;
* jugadores;
* jornadas.

El problema es que existe mucha funcionalidad duplicada respecto al cliente implementado dentro de `biwenger.py`.

La arquitectura objetivo debería tener **un único cliente de Biwenger**.

---

# 28. `config.py`

Gestiona variables de entorno mediante `python-dotenv`.

Variables necesarias:

```text
TELEGRAM_TOKEN
BIWENGER_USERNAME
BIWENGER_PASSWORD
```

El programa falla al arrancar si alguna no existe.

Esto es correcto desde el punto de vista de seguridad.

Nunca deben almacenarse credenciales directamente en el repositorio.

---

# 29. `requirements.txt`

Dependencias actuales:

```text
python-telegram-bot
requests
python-dotenv
Pillow
```

Son suficientes para la arquitectura actual.

---

# 30. Tests

Actualmente existen tres archivos relacionados con pruebas:

```text
test.py
test_client.py
test_alineaciones.py
```

## `test_alineaciones.py`

Es el test más útil actualmente.

Comprueba:

* alineación antes del partido;
* transición a alineación confirmada;
* uso de `initialLineups`.

## `test_client.py`

Está desactualizado respecto al cliente actual.

Utiliza métodos como:

```text
get_league_by_name()
league_by_secret()
```

que no corresponden a la implementación actual del cliente.

## `test.py`

También está desactualizado.

Utiliza:

```text
pybiwenger
```

y variables:

```text
BIWENGER_USER
BIWENGER_PASSWORD
```

mientras que el proyecto actual utiliza `requests` y:

```text
BIWENGER_USERNAME
BIWENGER_PASSWORD
```

Por tanto, estos tests no representan actualmente una suite fiable.

---

# 31. Problemas técnicos detectados

## 31.1 Dos clientes Biwenger

Tenemos:

```text
biwenger.py
    └── BiwengerClient
```

y:

```text
biwenger_client.py
    └── BiwengerClient
```

Esto debe terminar unificándose.

---

## 31.2 Dos sistemas de caché

Tenemos:

```text
biwenger.py
    └── caché en memoria
```

y:

```text
player_cache.py
    └── /app/players.json
```

Además `config.py` define:

```text
data/players.json
```

pero esa ruta no coincide con la implementación.

---

## 31.3 `biwenger.py` es demasiado grande

El módulo contiene acceso a API, transformación, cálculos, jornadas, mercado y presentación.

Funciona, pero dificulta:

* probar;
* depurar;
* modificar;
* detectar regresiones.

---

## 31.4 Determinación de jornada actual

Es una dependencia crítica para:

* puntos última jornada;
* media;
* jornadas;
* alineaciones;
* estadísticas.

Debe existir una única función fiable que determine:

```text
número de jornada actual
ID de la jornada actual
jornada anterior
```

---

## 31.5 Tests insuficientes

Necesitamos tests para:

* puntos por jornada;
* jornadas aplazadas;
* marcador;
* propietarios;
* mercado;
* caché;
* jornada actual;
* media;
* ausencia de report;
* partidos en directo;
* alineaciones.

---

# 32. Problema de despliegue conocido

El bot utiliza Telegram mediante polling.

Esto significa que solo puede existir una instancia haciendo:

```text
getUpdates
```

con el mismo token.

Si hay dos instancias activas aparece:

```text
409 Conflict
terminated by other getUpdates request
```

Por tanto, en Railway debe mantenerse una única instancia activa del bot.

---

# 33. Seguridad

Las credenciales de:

```text
TELEGRAM_TOKEN
BIWENGER_USERNAME
BIWENGER_PASSWORD
```

deben estar únicamente en variables de entorno.

El `.gitignore` ya excluye:

```text
.env
__pycache__/
*.pyc
.DS_Store
```

Nunca deben introducirse tokens o contraseñas en commits, logs o mensajes de diagnóstico.

---

# 34. Diagnóstico actualmente incorporado

`biwenger.py` contiene diagnóstico del cliente que registra:

* clase utilizada;
* archivo desde el que se carga;
* existencia del archivo;
* SHA256;
* existencia de `obtener_jornadas`.

Esto fue útil para comprobar qué versión estaba ejecutando Railway.

Una vez estabilizado el proyecto, este diagnóstico debería reducirse o convertirse en logging de depuración.

---

# 35. Flujo general de una consulta

Ejemplo: usuario pulsa un jugador.

```text
Telegram
   ↓
callback jugador:<id>
   ↓
bot.py
   ↓
obtener_ficha_jugador(id)
   ↓
mapa público de jugadores
   ↓
mapa de propietarios
   ↓
jornada actual
   ↓
jornada anterior
   ↓
reports
   ↓
cálculo de puntos
   ↓
cálculo de media
   ↓
texto de ficha
   ↓
Telegram
```

---

# 36. Arquitectura objetivo

La evolución recomendada sería separar:

```text
bot.py
```

Interfaz Telegram.

```text
services/
```

Lógica de negocio.

```text
clients/
```

Comunicación con Biwenger.

```text
repositories/
```

Cachés y almacenamiento.

```text
models/
```

Modelos normalizados.

```text
presentation/
```

Textos e imágenes.

Una arquitectura futura podría ser:

```text
bot.py
 │
 ├── services/
 │      ├── jugadores.py
 │      ├── mercado.py
 │      ├── jornadas.py
 │      ├── alineaciones.py
 │      └── informes.py
 │
 ├── clients/
 │      └── biwenger.py
 │
 ├── repositories/
 │      └── cache.py
 │
 └── presentation/
        ├── telegram.py
        └── alineaciones.py
```

No es necesario hacer esta refactorización inmediatamente.

Primero debemos estabilizar la lógica actual.

---

# 37. Orden recomendado de mejoras

## Fase 1 — Estabilizar datos

1. Definir correctamente la jornada actual.
2. Definir jornada anterior.
3. Validar puntos de última jornada.
4. Validar media.
5. Validar marcadores.
6. Validar propietarios.
7. Validar alineaciones.

## Fase 2 — Tests

Crear tests para todas las funciones críticas.

Especialmente:

```text
J1
J2
J3
jornadas aplazadas
partido terminado
partido en directo
partido pendiente
jugador sin report
jugador con report
```

## Fase 3 — Unificar cliente

Eliminar la duplicación:

```text
biwenger.py
biwenger_client.py
```

y dejar una única implementación.

## Fase 4 — Unificar caché

Decidir una única estrategia para:

```text
players
market
owners
rounds
```

## Fase 5 — Separar responsabilidades

Reducir el tamaño de `biwenger.py`.

## Fase 6 — Mejorar funcionalidad

Una vez estable la base:

* estadísticas;
* historial por jugador;
* evolución de precios;
* evolución de puntos;
* análisis de plantilla;
* comparativas;
* recomendaciones;
* informes económicos más precisos.

---

# 38. Regla importante para futuras modificaciones

Antes de modificar una función relacionada con Biwenger debemos comprobar:

1. Qué endpoint proporciona el dato.
2. Qué estructura real devuelve.
3. Si el dato pertenece a la API privada o pública.
4. Si el dato es actual o histórico.
5. Si existe caché.
6. Si existe una segunda implementación de la misma función.
7. Qué otras funciones dependen de ella.

Esto evitará continuar acumulando parches sobre lógica duplicada.

---

# 39. Estado actual

El proyecto **funciona y ya tiene una base funcional considerable**, especialmente en:

* Telegram;
* mercado;
* jugadores;
* propietarios;
* jornadas;
* resultados;
* alineaciones;
* imágenes.

La principal deuda técnica no es que falte funcionalidad, sino que parte de ella ha ido creciendo sobre una arquitectura que todavía no se ha consolidado.

El objetivo inmediato debe ser:

```text
DATOS CORRECTOS
      ↓
LÓGICA CORRECTA
      ↓
TESTS
      ↓
REFACTORIZACIÓN
      ↓
NUEVAS FUNCIONALIDADES
```

No al revés.

---

## 40. Próximo objetivo

Antes de añadir otra funcionalidad, debemos dejar completamente fiable este núcleo:

```text
jornada actual
       ↓
jornada anterior
       ↓
puntos del jugador
       ↓
puntos totales
       ↓
media
       ↓
ficha del jugador
```

Una vez este flujo sea fiable, podremos usarlo como base para todas las futuras estadísticas del bot.
