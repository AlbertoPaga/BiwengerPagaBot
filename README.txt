# DOCUMENTACIÓN TÉCNICA — BiwengerPagaBot

1. DESCRIPCIÓN GENERAL DEL PROYECTO

---

BiwengerPagaBot es un bot de Telegram conectado con la API de Biwenger.

Su objetivo actual es permitir desde Telegram:

* Seleccionar una liga de Biwenger.
* Consultar los usuarios de una liga.
* Consultar los movimientos del mercado.
* Traducir los IDs de jugadores de Biwenger a nombres reales.
* Preparar la base para generar informes económicos de los participantes.
* Preparar posteriormente cálculos de compras, ventas, dinero disponible, valor de plantilla y patrimonio.

La arquitectura está separada en varias capas:

Telegram
↓
bot.py
↓
biwenger.py
↓
biwenger_client.py
↓
API de Biwenger

Y, paralelamente:

biwenger.py
↓
player_cache.py
↓
API pública de jugadores
↓
players.json

2. ARCHIVOS DEL PROYECTO

---

Actualmente se han proporcionado estos archivos:

* bot.py
* config.py
* biwenger.py
* biwenger_client.py
* player_cache.py
* test.py
* requirements.txt

Además, existe una configuración prevista para:

* data/players.json
* data/market.json

aunque actualmente el código de player_cache.py utiliza una ruta diferente:

/app/players.json

Esto es importante y se explica más adelante.

3. bot.py

---

## RESPONSABILIDAD

bot.py es la capa de interfaz con Telegram.

No debería encargarse directamente de hablar con la API de Biwenger.

Su función es:

1. Recibir comandos de Telegram.
2. Comprobar qué liga ha seleccionado el usuario.
3. Llamar a las funciones de biwenger.py.
4. Formatear los datos recibidos.
5. Enviar la respuesta al usuario.

## IMPORTACIONES

import logging

Se utiliza para registrar errores y problemas del bot.

De telegram se importan:

InlineKeyboardButton
InlineKeyboardMarkup

Sirven para crear el menú de selección de liga mediante botones.

De telegram.ext se importan:

Application
CommandHandler
CallbackQueryHandler
ContextTypes

Application:
Crea y ejecuta la aplicación de Telegram.

CommandHandler:
Asocia comandos como /liga o /informe a funciones.

CallbackQueryHandler:
Permite reaccionar cuando el usuario pulsa un botón.

ContextTypes:
Está importado pero actualmente no se utiliza explícitamente en las funciones.

También se importa:

TELEGRAM_TOKEN

desde config.py.

Finalmente:

obtener_ligas
cargar_liga

desde biwenger.py.

4. MAX_TELEGRAM

---

MAX_TELEGRAM = 4000

Telegram limita la longitud de los mensajes.

El bot utiliza 4000 caracteres como límite interno para evitar enviar mensajes demasiado largos.

5. enviar_largo()

---

Firma:

async def enviar_largo(update, texto)

Función auxiliar para enviar textos largos.

Funcionamiento:

1. Comprueba si el texto está vacío.

2. Si está vacío, utiliza:

   "Sin datos"

3. Divide el texto en bloques de 4000 caracteres.

4. Envía cada bloque mediante:

   update.message.reply_text()

Esto permite que informes o listados largos no fallen por superar el límite de Telegram.

6. start()

---

Función asociada al comando:

/start

Muestra al usuario un mensaje indicando que el bot está activo.

Actualmente muestra:

/liga
/informe
/movimientos
/ayuda

No realiza ninguna llamada a Biwenger.

7. liga()

---

Función asociada al comando:

/liga

Su objetivo es permitir al usuario seleccionar una liga.

Funcionamiento:

1. Llama a:

   obtener_ligas()

2. Recibe las ligas disponibles para la cuenta de Biwenger.

3. Crea un botón de Telegram para cada liga.

Cada botón contiene:

* nombre de la liga
* ID de la liga como callback_data

4. Envía los botones al usuario.

Si ocurre una excepción:

* se registra mediante logging.exception()
* se informa al usuario mediante Telegram.

8. elegir_liga()

---

Es el callback que se ejecuta cuando el usuario pulsa uno de los botones creados por /liga.

Obtiene:

query.data

que contiene el ID de la liga.

Lo convierte a entero:

liga_id = int(query.data)

Después guarda la liga seleccionada en:

context.user_data["liga"]

Esto es importante.

La liga seleccionada queda asociada a la conversación/usuario de Telegram.

A partir de ese momento /informe y /movimientos pueden saber qué liga utilizar.

Finalmente edita el mensaje original y muestra:

"✅ Liga seleccionada"

9. informe()

---

Función asociada al comando:

/informe

Primero intenta recuperar:

context.user_data["liga"]

Si no existe:

"Usa primero /liga"

y termina.

Si existe:

1. Llama a:

   cargar_liga(liga_id)

2. Recibe:

   usuarios, movimientos

3. Genera un texto:

   🏆 USUARIOS LIGA

4. Recorre los usuarios.

Actualmente solamente muestra:

• nombre

Por tanto, aunque la función se llama /informe, el informe económico todavía no está implementado aquí.

Actualmente NO calcula:

* compras
* ventas
* dinero
* valor de plantilla
* patrimonio
* ranking económico

La estructura actual es únicamente un listado de usuarios.

Este es precisamente uno de los puntos que posteriormente se puede mejorar sin tocar la selección de liga ni el funcionamiento del mercado.

10. movimientos()

---

Función asociada al comando:

/movimientos

Primero comprueba que exista una liga seleccionada.

Después llama a:

cargar_liga(liga_id)

Recibe:

usuarios, movs

Ignora los usuarios y utiliza únicamente:

movs

Genera:

🔄 MOVIMIENTOS

y añade cada movimiento recibido.

Por tanto, actualmente el procesamiento visual de los movimientos está delegado en:

biwenger.py

11. ayuda()

---

Función asociada a:

/ayuda

Muestra la lista de comandos disponibles.

No realiza ninguna llamada a Biwenger.

12. error_handler()

---

Es el manejador global de errores de Telegram.

Recibe:

update
context

y registra:

context.error

mediante logging.

Actualmente no envía un mensaje al usuario.

13. main()

---

Es el punto de entrada del bot.

Crea:

Application.builder().token(TELEGRAM_TOKEN).build()

Después registra:

/start
/liga
/informe
/movimientos
/ayuda

También registra:

CallbackQueryHandler(elegir_liga)

y:

app.add_error_handler(error_handler)

Finalmente ejecuta:

app.run_polling(drop_pending_updates=True)

Por tanto, el bot funciona mediante polling.

14. config.py

---

## RESPONSABILIDAD

config.py centraliza la configuración y las variables de entorno.

15. dotenv

---

Se utiliza:

from dotenv import load_dotenv

load_dotenv()

Esto permite cargar las variables desde un archivo .env.

16. obtener_variable()

---

Función:

obtener_variable(nombre)

Busca una variable de entorno mediante:

os.getenv(nombre)

Si no existe o está vacía:

raise RuntimeError(...)

Esto evita que el programa arranque sin las credenciales necesarias.

17. VARIABLES DE TELEGRAM

---

TELEGRAM_TOKEN

Contiene el token del bot de Telegram.

No debe guardarse directamente en el código fuente.

18. VARIABLES DE BIWENGER

---

BIWENGER_USERNAME
BIWENGER_PASSWORD

Contienen las credenciales utilizadas para autenticarse contra Biwenger.

Deben mantenerse fuera del código y nunca publicarse.

19. CONFIGURACIÓN DE CACHÉ

---

El archivo define:

PLAYERS_CACHE_FILE = "data/players.json"

MARKET_CACHE_FILE = "data/market.json"

PLAYERS_CACHE_HOURS = 24

La intención es:

* guardar jugadores en caché
* guardar mercado en caché
* considerar válida la caché de jugadores durante 24 horas

IMPORTANTE:

En el código actual de player_cache.py NO se utilizan estas variables.

player_cache.py utiliza directamente:

/app/players.json

Por tanto existe una discrepancia entre la configuración y la implementación.

20. biwenger.py

---

## RESPONSABILIDAD

biwenger.py es la capa de lógica de negocio entre el bot y Biwenger.

El bot no debería conocer detalles de URLs, headers o autenticación.

En cambio, bot.py llama a:

obtener_ligas()
cargar_liga()

y biwenger.py se encarga de obtener y preparar los datos.

21. obtener_ligas()

---

Crea un BiwengerClient:

client = BiwengerClient()

Hace login:

client.login()

Y devuelve:

client.leagues()

Por tanto, su finalidad es obtener las ligas disponibles para la cuenta autenticada.

22. cargar_liga()

---

Actualmente recibe:

liga_id

Crea un BiwengerClient.

Hace login.

Obtiene la información básica de la liga mediante:

client.league(liga_id)

Después imprime por consola información de depuración.

Entre otras cosas muestra:

* contenido completo de la liga
* claves existentes en data
* tipo de cada campo
* cantidad de elementos si es una lista
* número de claves si es un diccionario

Esto se utilizó durante la fase de investigación de la API.

Después busca los usuarios.

Primero:

if "users" in data

Después contempla:

members
managers

Esto proporciona cierta tolerancia ante posibles estructuras diferentes de respuesta.

Finalmente llama a:

cargar_movimientos(client, liga_id)

y devuelve:

(
usuarios,
movimientos
)

IMPORTANTE:

Actualmente cargar_liga() NO carga las plantillas.

Tampoco calcula todavía compras, ventas ni patrimonio.

Esto es lo que debe ampliarse para construir el informe económico.

23. cargar_movimientos()

---

Recibe:

client
liga_id

Llama a:

client.board(liga_id)

Obtiene:

board["data"]

Comprueba que sea una lista.

Durante la fase de desarrollo imprime:

* tipo de data
* número de elementos
* primeros movimientos
* type
* content

Después llama a:

formatear_movimientos(data)

24. formatear_movimientos()

---

Esta función transforma los eventos RAW de Biwenger en textos legibles para Telegram.

Recibe una lista de movimientos.

Para cada evento obtiene:

type
content

Los tipos actualmente tratados son:

* market
* transfer
* playerMovements

25. MOVIMIENTOS "market" Y "transfer"

---

Para cada movimiento obtiene:

player

amount

to

from

El ID del jugador se transforma en nombre mediante:

get_player_name(player_id)

de player_cache.py.

26. COMPRA

---

Si existe:

item["to"]

se considera que existe comprador.

Se genera:

🟢 [comprador] ficha a [jugador] por [cantidad]€

Ejemplo conceptual:

🟢 BertetePorro ficha a X por 500.000€

27. VENTA

---

Si existe:

item["from"]

se considera que existe vendedor.

Se genera:

🔴 [vendedor] vende a [jugador] por [cantidad]€

28. MOVIMIENTO SIN COMPRADOR/VENDEDOR

---

Si no existe ninguno de los anteriores:

⚽ Movimiento de [jugador] ([cantidad]€)

29. playerMovements

---

Este tipo representa movimientos relacionados con cambios de plantilla.

Actualmente genera:

🔄 Cambio de [jugador]

No realiza cálculos económicos.

30. LÍMITE DE MOVIMIENTOS

---

formatear_movimientos() devuelve:

resultado[:30]

Por tanto, como máximo se muestran 30 movimientos.

31. patrimonio()

---

Actualmente recibe un usuario.

Obtiene:

balance
teamValue

y devuelve:

dinero
valor
dinero + valor

Es decir:

dinero = balance

valor = teamValue

patrimonio = balance + teamValue

IMPORTANTE:

Esta función existe, pero todavía no está integrada en el informe de Telegram.

32. biwenger_client.py

---

En los archivos proporcionados, biwenger_client.py contiene el método:

league_players()

Este método es especialmente importante para la futura generación del informe.

33. league_players()

---

Firma:

def league_players(self, league_id)

Su objetivo es obtener las plantillas de todos los usuarios de una liga.

Primero obtiene el usuario asociado a la liga:

user_id = self.find_league_user(league_id)

Después establece el contexto:

self.set_context(
league_id,
user_id
)

Después hace login.

Construye manualmente los headers:

Authorization
Accept
X-League
X-User

Esto es importante porque durante las pruebas de la API se descubrió que la petición:

/league/{liga_id}?fields=users(players)

sin los headers:

X-League
X-User

devuelve:

400
X-League and X-User headers required

34. IMPORTANCIA DE X-LEAGUE Y X-USER

---

Este fue uno de los descubrimientos importantes durante el desarrollo.

Una petición directa como:

/league/2158595?fields=users(players)

sin contexto produce:

HTTP 400

con:

X-League and X-User headers required

Cuando se añaden:

X-League
X-User
Authorization

la petición funciona y devuelve:

users -> players -> id

35. RESPUESTA DE league_players()

---

La respuesta obtenida tiene una estructura similar a:

data
users
players
id

Cada usuario aparece en el mismo orden que los usuarios de la liga.

Ejemplo conceptual:

data:
users:
usuario 1:
players:
id 1876
id 8747
...

```
    usuario 2:
        players:
            id 1721
            id 2184
            ...
```

## 36. PROBLEMA IMPORTANTE CON LA RESPUESTA

La respuesta de:

league_players()

no proporciona directamente el nombre del usuario dentro de cada elemento.

La relación se realiza mediante el orden de los usuarios.

Por tanto, para asociar:

usuario -> jugadores

hay que tener previamente la lista de usuarios de:

client.league(liga_id)

y utilizar el mismo orden.

Esto es similar a la implementación del proyecto anterior que utilizaba:

ids = list(usuarios.keys())

y posteriormente:

uid = ids[i]

37. player_cache.py

---

## RESPONSABILIDAD

player_cache.py se encarga de traducir IDs numéricos de jugadores a nombres reales.

Esto es necesario porque los movimientos del board de Biwenger contienen:

player: 27929

en lugar de:

player: "Nombre del jugador"

38. PLAYERS_FILE

---

Actualmente está definido como:

Path("/app/players.json")

Esto significa que el código intenta guardar y leer la caché desde:

/app/players.json

En desarrollo local en Mac esto provoca un problema porque:

/app

no es un directorio normal de escritura.

Durante las pruebas se produjo:

FileNotFoundError:
No such file or directory: '/app/players.json'

y posteriormente:

mkdir: /app: Read-only file system

39. cargar_jugadores()

---

Esta función descarga los jugadores desde Biwenger mediante:

client.players()

Después intenta obtener:

data["players"]

La API puede devolver los jugadores como:

* diccionario
* lista

El código contempla ambos formatos.

40. ESTRUCTURA DE LA CACHÉ

---

Cada jugador se almacena conceptualmente como:

{
"12345": {
"name": "Nombre",
"team": {...}
}
}

Finalmente se escribe:

{
"players": jugadores
}

en:

/app/players.json

41. cargar_cache()

---

Comprueba primero si existe:

PLAYERS_FILE

Si no existe:

llama a:

cargar_jugadores()

Si existe:

abre el JSON y devuelve:

datos["players"]

42. actualizar_cache()

---

Es simplemente un alias práctico para:

cargar_jugadores()

Su objetivo es forzar una actualización de la caché.

43. get_player_name()

---

Recibe:

player_id

Carga la caché.

Busca:

str(player_id)

Si existe:

devuelve el campo:

name

Si no existe:

devuelve:

Jugador [ID]

Por eso actualmente los movimientos pueden mostrar nombres reales cuando la caché está disponible y "Jugador 27929" cuando no lo está.

44. DESCUBRIMIENTO SOBRE LOS NOMBRES

---

Durante las pruebas se comprobó que la lógica de nombres estaba funcionando.

Los movimientos recibidos tenían IDs como:

27929
8555
10182
31267
...

y el código intentaba resolverlos mediante:

get_player_name()

La intención correcta es mantener esta funcionalidad separada de la lógica de informes.

45. test.py

---

El test.py actual es:

import pybiwenger

from pybiwenger import LeagueAPI

from config import BIWENGER_USER, BIWENGER_PASSWORD

...

Este archivo pertenece a una versión anterior del proyecto.

Utiliza:

pybiwenger

y las variables:

BIWENGER_USER
BIWENGER_PASSWORD

Pero la configuración actual utiliza:

BIWENGER_USERNAME
BIWENGER_PASSWORD

Por tanto, test.py NO está alineado con la arquitectura actual.

46. CONSECUENCIA DE test.py

---

El proyecto actual utiliza un cliente propio:

BiwengerClient

mientras que test.py utiliza:

pybiwenger

Por tanto test.py debería considerarse:

TEST ANTIGUO / LEGACY

No debería utilizarse como referencia para modificar la arquitectura actual.

47. requirements.txt

---

Actualmente contiene:

python-telegram-bot
requests
python-dotenv

Estas son las dependencias principales de la arquitectura actual.

48. python-telegram-bot

---

Se utiliza para:

* crear el bot
* recibir comandos
* crear botones
* gestionar callbacks
* enviar mensajes
* ejecutar polling

49. requests

---

Se utiliza para realizar peticiones HTTP a Biwenger.

El cliente propio utiliza:

requests.Session()

50. python-dotenv

---

Permite cargar las variables del archivo:

.env

mediante:

load_dotenv()

51. ARQUITECTURA ACTUAL

---

La arquitectura lógica actual es:

```
                TELEGRAM
                   │
                   ▼
                bot.py
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
  obtener_ligas()       cargar_liga()
                              │
                              ▼
                     BiwengerClient
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
          API privada                 API jugadores
                │                           │
                ▼                           ▼
          Liga / Board               player_cache
                │                           │
                ▼                           ▼
         movimientos                  players.json
                │
                ▼
       formatear_movimientos()
                │
                ▼
             bot.py
                │
                ▼
            Telegram
```

## 52. FLUJO DE /LIGA

Usuario:

/liga

```
    ↓
```

bot.py

```
    ↓
```

obtener_ligas()

```
    ↓
```

BiwengerClient.login()

```
    ↓
```

BiwengerClient.leagues()

```
    ↓
```

API /account

```
    ↓
```

lista de ligas

```
    ↓
```

bot.py

```
    ↓
```

botones de Telegram

```
    ↓
```

usuario selecciona una liga

```
    ↓
```

elegir_liga()

```
    ↓
```

context.user_data["liga"] = liga_id

53. FLUJO DE /MOVIMIENTOS

---

Usuario:

/movimientos

```
    ↓
```

bot.py

```
    ↓
```

comprueba liga seleccionada

```
    ↓
```

cargar_liga(liga_id)

```
    ↓
```

client.league(liga_id)

```
    ↓
```

obtención de usuarios

```
    ↓
```

client.board(liga_id)

```
    ↓
```

obtención del tablón

```
    ↓
```

formatear_movimientos()

```
    ↓
```

get_player_name()

```
    ↓
```

player_cache

```
    ↓
```

texto final

```
    ↓
```

Telegram

54. FLUJO DE /INFORME ACTUAL

---

Usuario:

/informe

```
    ↓
```

bot.py

```
    ↓
```

cargar_liga(liga_id)

```
    ↓
```

obtención de usuarios

```
    ↓
```

obtención de movimientos

```
    ↓
```

bot.py

```
    ↓
```

muestra solamente:

🏆 USUARIOS LIGA

• Usuario 1
• Usuario 2
• Usuario 3
...

55. LO QUE EL INFORME TODAVÍA NO HACE

---

Actualmente /informe NO realiza el informe económico completo.

No calcula todavía:

* total comprado por usuario
* total vendido por usuario
* número de operaciones
* lista de jugadores comprados
* lista de jugadores vendidos
* dinero disponible calculado
* valor real de plantilla
* patrimonio total
* posición económica
* ranking
* diferencia respecto al resto
* estadísticas del mercado

56. INFORME QUE SE PREPARABA EN EL PROYECTO ANTERIOR

---

En el proyecto anterior existía una estructura mucho más orientada al informe.

Cada usuario tenía:

{
"nombre": ...,
"compras": 0,
"ventas": 0,
"comprados": [],
"vendidos": []
}

Esto permitía acumular todas las operaciones.

Ejemplo:

usuario["compras"] += cantidad

usuario["ventas"] += cantidad

y además:

usuario["comprados"].append(
(nombre, cantidad)
)

usuario["vendidos"].append(
(nombre, cantidad)
)

57. CÁLCULO DE DINERO DEL PROYECTO ANTERIOR

---

El proyecto anterior utilizaba:

dinero =
20.000.000
+ ventas
- compras

Esto supone una lógica basada en un presupuesto inicial de:

20.000.000 €

Por tanto:

Dinero disponible =
presupuesto inicial

* dinero obtenido por ventas

- dinero gastado en compras

58. VALOR DE PLANTILLA DEL PROYECTO ANTERIOR

---

Se calculaba sumando el precio de todos los jugadores:

valor = sum(
jugador.price
for jugador in plantilla
)

Después:

patrimonio =
dinero
+ valor de plantilla

59. DIFERENCIA CON EL CÓDIGO ACTUAL

---

El código actual tiene:

patrimonio(usuario)

que utiliza:

usuario["balance"]
usuario["teamValue"]

Pero todavía no se está utilizando:

league_players()

para construir el valor de cada plantilla.

Por tanto hay dos posibles fuentes de información:

1. Datos económicos que proporciona directamente Biwenger.
2. Cálculo propio a partir de compras, ventas y jugadores actuales.

La elección debe hacerse antes de implementar definitivamente el informe.

60. DESCUBRIMIENTO CLAVE PARA LAS PLANTILLAS

---

Actualmente sabemos que funciona una petición como:

GET:

/api/v2/league/{liga_id}

con:

fields=users(players)

y headers:

Authorization: Bearer TOKEN
Accept: application/json
X-League: liga_id
X-User: user_id

61. RESULTADO DE PLANTILLAS

---

El resultado contiene:

users
└── players
├── id
├── id
├── id
└── ...

Esto permite saber qué jugadores tiene actualmente cada participante.

62. QUÉ FALTA PARA COMPLETAR EL INFORME

---

La información necesaria ya está prácticamente disponible.

Tenemos:

A) Usuarios de la liga
→ client.league()

B) Movimientos del mercado
→ client.board()

C) IDs de jugadores
→ board y league_players()

D) Nombres de jugadores
→ player_cache

E) Plantillas actuales
→ league_players()

F) Datos económicos potenciales
→ balance / teamValue si vienen disponibles

Por tanto, el siguiente paso natural es una función de lógica de negocio que combine estos datos.

63. POSIBLE ESTRUCTURA DEL INFORME FUTURO

---

Para cada usuario:

NOMBRE

💰 Dinero:
X €

👥 Valor plantilla:
X €

🏦 Patrimonio:
X €

📈 Compras:
X €

📉 Ventas:
X €

⚽ Jugadores:

* Jugador 1
* Jugador 2
* Jugador 3

🟢 Compras realizadas:

* Jugador X — 500.000 €
* Jugador Y — 1.200.000 €

🔴 Ventas realizadas:

* Jugador Z — 800.000 €

64. PUNTOS QUE NO SE DEBEN TOCAR SIN NECESIDAD

---

Hay varias piezas que ya han sido probadas y funcionan.

Especialmente:

1. Login de Biwenger.

2. Obtención de ligas.

3. Selección de liga en Telegram.

4. Obtención del board.

5. Lectura de movimientos.

6. Resolución de nombres mediante player_cache.

7. Petición de plantillas utilizando:
   fields=users(players)

8. Headers:
   X-League
   X-User
   Authorization

9. ERROR 401 DESCUBIERTO

---

Durante las pruebas se produjo:

401 Unauthorized

cuando se utilizaron credenciales incorrectas.

Después, con las credenciales correctas, el login funcionó.

Por tanto, un error 401 durante pruebas puede ser simplemente un problema de credenciales.

66. ERROR 400 DESCUBIERTO

---

Se produjo:

400 Client Error

con:

X-League and X-User headers required

cuando se intentó:

/league/{liga_id}?fields=users(players)

sin enviar el contexto necesario.

La solución descubierta fue proporcionar:

X-League
X-User
Authorization

67. ERROR DE CACHE /app

---

El sistema local produjo:

FileNotFoundError:

/app/players.json

y posteriormente:

Read-only file system

Esto indica que la ruta:

/app/players.json

no es adecuada para desarrollo local en Mac.

La configuración ya contiene:

PLAYERS_CACHE_FILE = "data/players.json"

pero player_cache.py no utiliza todavía esta variable.

La futura solución lógica sería centralizar la ruta en config.py y utilizarla desde player_cache.py.

68. ESTADO DEL CACHE DE JUGADORES

---

El cache es útil y debe mantenerse.

No es necesario eliminarlo.

Su función es simplemente evitar tener que consultar la API pública de jugadores cada vez que se procesa un movimiento.

La arquitectura correcta debería ser:

Movimiento:
player_id = 27929

```
    ↓
```

get_player_name(27929)

```
    ↓
```

cache

```
    ↓
```

"Nombre real"

69. PROBLEMA DE CARGAR_CACHE()

---

Actualmente cada llamada a:

get_player_name()

llama a:

cargar_cache()

Si hay muchos movimientos, esto puede implicar abrir el JSON repetidamente.

No necesariamente es un problema con pocos movimientos, pero puede optimizarse manteniendo la caché en memoria.

No es prioritario mientras el sistema funcione.

70. ESTADO DE BIWENGER.PY

---

biwenger.py funciona actualmente como una capa de procesamiento básica.

Está en una fase intermedia:

* login: funciona
* ligas: funciona
* usuarios: funciona
* board: funciona
* movimientos: funciona
* nombres: funciona si cache está disponible
* plantillas: el cliente ya tiene preparado el método
* informe económico: pendiente

71. ESTADO DE BIWENGER_CLIENT.PY

---

El código proporcionado de este archivo contiene específicamente:

league_players()

No se ha incluido en este último volcado el resto de la clase BiwengerClient.

Por tanto, esta documentación solo puede afirmar con certeza sobre el método proporcionado.

Según las pruebas realizadas anteriormente, la clase actual dispone de métodos para:

* login
* get
* account
* leagues
* find_league_user
* league
* board
* players
* league_players

La responsabilidad del cliente es encapsular la comunicación HTTP con Biwenger.

72. SEPARACIÓN API PRIVADA / API PÚBLICA

---

El diseño utiliza dos sesiones HTTP.

API privada:

self.session

Se utiliza para:

* login
* cuenta
* ligas
* liga
* board
* plantillas

Esta sesión utiliza autenticación.

API pública:

self.public_session

Se utiliza para:

* obtener datos públicos de jugadores.

No debe utilizarse el token privado innecesariamente para la API pública.

73. SEGURIDAD

---

Las credenciales deben mantenerse exclusivamente en variables de entorno.

Nunca guardar en el código:

BIWENGER_USERNAME = "..."
BIWENGER_PASSWORD = "..."
TELEGRAM_TOKEN = "..."

El archivo .env tampoco debería subirse al repositorio.

También debe evitarse imprimir tokens en logs.

74. TEST.PY — ESTADO

---

test.py es antiguo.

Está basado en:

pybiwenger

y:

LeagueAPI

Actualmente la aplicación principal utiliza:

BiwengerClient

Por tanto, test.py debería actualizarse o sustituirse si se quiere mantener una suite de pruebas coherente.

75. REQUIREMENTS.TXT

---

Las dependencias actuales son suficientes para la arquitectura propia:

python-telegram-bot
requests
python-dotenv

pybiwenger NO aparece en requirements.txt.

Esto confirma que el código principal ya no debería depender de pybiwenger.

76. FLUJO COMPLETO DEL PROYECTO

---

1. Arranca bot.py.

2. config.py carga .env.

3. Se obtiene TELEGRAM_TOKEN.

4. Se crea Application.

5. El bot empieza polling.

6. Usuario ejecuta /liga.

7. bot.py llama obtener_ligas().

8. biwenger.py crea BiwengerClient.

9. BiwengerClient realiza login.

10. Se obtiene la cuenta de Biwenger.

11. Se devuelven las ligas.

12. Telegram muestra botones.

13. Usuario selecciona una liga.

14. El ID se guarda en:
    context.user_data["liga"]

15. Usuario ejecuta /movimientos o /informe.

16. bot.py recupera el ID.

17. Llama a cargar_liga().

18. cargar_liga() obtiene información de la liga.

19. Obtiene usuarios.

20. Obtiene el board.

21. Procesa los movimientos.

22. Para cada jugador se consulta el cache.

23. Se obtiene el nombre.

24. Se genera texto.

25. bot.py envía el resultado a Telegram.

26. ARQUITECTURA DE RESPONSABILIDADES

---

## bot.py

Interfaz Telegram.

## config.py

Configuración y secretos.

## biwenger_client.py

Comunicación HTTP con Biwenger.

## biwenger.py

Lógica de negocio y transformación de datos.

## player_cache.py

Resolución/cache de jugadores.

## test.py

Prueba antigua basada en pybiwenger.

## requirements.txt

Dependencias Python.

78. PRINCIPIO IMPORTANTE PARA FUTURAS MODIFICACIONES

---

No conviene meter toda la lógica en bot.py.

La arquitectura debería mantenerse:

bot.py
↓
biwenger.py
↓
biwenger_client.py

y:

biwenger.py
↓
player_cache.py

79. PRÓXIMO PASO RECOMENDADO

---

El siguiente trabajo debería centrarse exclusivamente en el INFORME.

No es necesario modificar:

* selección de liga
* autenticación
* board
* nombres
* funcionamiento general del bot
* API pública de jugadores

La mejora debería consistir en:

1. Obtener usuarios.

2. Obtener movimientos.

3. Obtener plantillas.

4. Crear un catálogo de jugadores.

5. Asociar cada plantilla con su usuario.

6. Calcular compras.

7. Calcular ventas.

8. Calcular dinero.

9. Calcular valor de plantilla.

10. Calcular patrimonio.

11. Ordenar los usuarios.

12. Formatear el informe para Telegram.

13. OBJETIVO FINAL

---

El bot debería terminar produciendo algo similar a:

🏆 INFORME DE LA LIGA

1️⃣ Usuario A
💰 Dinero: 5.200.000 €
👥 Plantilla: 17.400.000 €
🏦 Patrimonio: 22.600.000 €
📈 Compras: 8.300.000 €
📉 Ventas: 4.500.000 €

2️⃣ Usuario B
💰 Dinero: 3.100.000 €
👥 Plantilla: 19.200.000 €
🏦 Patrimonio: 22.300.000 €
📈 Compras: 10.100.000 €
📉 Ventas: 6.200.000 €

etc.

81. RESUMEN DEL ESTADO ACTUAL

---

🟢 FUNCIONANDO / COMPROBADO

* Autenticación contra Biwenger.
* Obtención de ligas.
* Selección de liga desde Telegram.
* Obtención de información de liga.
* Obtención del board.
* Lectura de movimientos.
* Identificación de comprador/vendedor.
* Resolución de nombres de jugadores cuando la caché está disponible.
* API pública de jugadores.
* Petición de usuarios con jugadores mediante:
  fields=users(players)
* Uso correcto de X-League.
* Uso correcto de X-User.
* Bot de Telegram.
* Comandos básicos.

🟡 PARCIAL / PENDIENTE

* Informe económico.
* Cálculo de compras.
* Cálculo de ventas.
* Asociación completa usuario → plantilla.
* Cálculo de valor de plantilla.
* Ranking por patrimonio.
* Informe detallado.
* Caché configurable mediante config.py.
* Optimización de lectura del cache.

🔴 OBSERVACIONES / PROBLEMAS CONOCIDOS

* player_cache.py utiliza /app/players.json.
* config.py define otra ruta: data/players.json.
* test.py utiliza la arquitectura antigua pybiwenger.
* test.py utiliza nombres de variables que ya no coinciden con config.py.
* biwenger.py todavía tiene mucho código de depuración mediante print().
* /informe actualmente solo lista nombres.
* El método league_players() está preparado pero todavía no está integrado en cargar_liga().

82. CONCLUSIÓN

---

El proyecto ya tiene construida la parte más delicada de comunicación con Biwenger.

La autenticación, selección de liga, lectura del mercado y resolución de nombres están separadas correctamente.

El descubrimiento más importante para continuar es que Biwenger permite obtener las plantillas mediante:

/league/{liga_id}?fields=users(players)

pero exige los headers:

X-League
X-User

además de la autorización.

Esto ya está resuelto en league_players().

Por tanto, el siguiente objetivo no debería ser modificar clientes ni rehacer la comunicación con Biwenger.

El siguiente objetivo debería ser exclusivamente construir la capa de INFORME en biwenger.py utilizando los datos que ya tenemos.

La idea es:

DATOS DE LIGA
+
MOVIMIENTOS
+
PLANTILLAS
+
NOMBRES DE JUGADORES
↓
PROCESAMIENTO
↓
COMPRAS / VENTAS / DINERO / VALOR PLANTILLA
↓
PATRIMONIO
↓
RANKING
↓
INFORME TELEGRAM

83. NOTA SOBRE EL PROYECTO ANTERIOR

---

El proyecto anterior es especialmente útil como referencia para la lógica de negocio.

Su estructura:

usuarios
compras
ventas
comprados
vendidos

plantillas

patrimonio()

es una buena base conceptual para reconstruir el informe actual.

Sin embargo, no debe copiarse directamente la comunicación API del proyecto antiguo porque actualmente existe un cliente propio:

BiwengerClient

y ya se ha comprobado cómo funciona la API actual.

La estrategia correcta es conservar:

* la arquitectura HTTP actual
* el cliente actual
* el cache actual

y recuperar del proyecto anterior únicamente la lógica de cálculo del informe.

84. REGLA DE ORO PARA CONTINUAR

---

NO TOCAR lo que ya está funcionando para obtener:

* login
* ligas
* usuarios
* mercado
* nombres

salvo que sea estrictamente necesario.

Construir encima de eso la lógica de:

* plantillas
* compras
* ventas
* patrimonio
* informe.

De esta manera se reduce muchísimo el riesgo de romper la parte funcional del bot.
