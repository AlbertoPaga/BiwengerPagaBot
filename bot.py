import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import TELEGRAM_TOKEN

from biwenger import (
    obtener_ligas,
    obtener_informe,
    obtener_mercado_completo_datos,
    obtener_mercado_24h_datos,
    obtener_mercado_hoy_datos,
    obtener_miembros_liga,
    obtener_mercado_miembro_datos,
    obtener_ficha_jugador,
    obtener_jornadas,
    obtener_jornada,
    obtener_jornada_actual,
    _timestamp_partido,
)


from lineup_image import (
    LineupImageError,
    obtener_alineacion_mostrable,
    generar_imagen_alineacion,
)

from datetime import datetime
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo(
    "Europe/Madrid"
)

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(
    __name__
)

MAX_TELEGRAM = 4000

POSICIONES_MERCADO_HOY = {
    "DL": {
        "boton": "DEL",
        "titulo": "⚽ DELANTEROS",
    },
    "MC": {
        "boton": "MC",
        "titulo": "🧠 MEDIOCENTROS",
    },
    "DF": {
        "boton": "DF",
        "titulo": "🛡️ DEFENSAS",
    },
    "PT": {
        "boton": "PT",
        "titulo": "🧤 PORTEROS",
    },
}

POSICIONES_MERCADO_HOY_ORDEN = (
    "DL",
    "MC",
    "DF",
    "PT",
)

POSICION_TODAS = "TODAS"

JUGADORES_POR_PAGINA = 6
JORNADAS_POR_PAGINA = 9


def _nombre_equipo(valor, defecto):
    if isinstance(valor, dict):
        return (
            valor.get("name")
            or valor.get("shortName")
            or str(valor.get("id") or defecto)
        )
    return str(valor or defecto)


def _resultado_partido(partido):
    if not isinstance(partido, dict):
        return None, None, None

    score = partido.get("score")

    local = None
    visitante = None

    if isinstance(score, dict):
        local = (
            score.get("home")
            if score.get("home") is not None
            else score.get("local")
        )

        visitante = (
            score.get("away")
            if score.get("away") is not None
            else score.get("visitante")
        )

        if local is None:
            local = score.get("homeScore")

        if visitante is None:
            visitante = score.get("awayScore")

    elif isinstance(score, (list, tuple)) and len(score) >= 2:
        local = score[0]
        visitante = score[1]

    status = partido.get("status")

    if isinstance(status, dict):
        status = (
            status.get("name")
            or status.get("short")
            or status.get("status")
            or status.get("value")
        )

    if status is None:
        status = (
            partido.get("state")
            or partido.get("estado")
        )

    return local, visitante, status

def teclado_jornadas(
    jornadas,
    pagina=0,
):
    """
    Construye el selector paginado de jornadas.
    """

    if not isinstance(
        jornadas,
        list,
    ):
        jornadas = []

    total = len(
        jornadas
    )

    total_paginas = max(
        1,
        (
            total
            + JORNADAS_POR_PAGINA
            - 1
        )
        // JORNADAS_POR_PAGINA,
    )

    try:

        pagina = int(
            pagina
        )

    except (
        TypeError,
        ValueError,
    ):

        pagina = 0

    pagina = max(
        0,
        min(
            pagina,
            total_paginas - 1,
        ),
    )

    inicio = (
        pagina
        * JORNADAS_POR_PAGINA
    )

    fin = (
        inicio
        + JORNADAS_POR_PAGINA
    )

    jornadas_pagina = jornadas[
        inicio:fin
    ]

    botones = []

    fila = []

    for jornada in jornadas_pagina:

        if not isinstance(
            jornada,
            dict,
        ):
            continue

        jornada_id = jornada.get(
            "id"
        )

        short = jornada.get(
            "short",
            "J?",
        )

        if jornada_id is None:
            continue

        # -------------------------------------------------
        # Detectar jornada aplazada
        # -------------------------------------------------

        games = jornada.get(
            "games",
            [],
        )

        if not isinstance(games, list):
            games = []

        texto_jornada = " ".join(
            str(
                jornada.get(
                    clave,
                    "",
                )
            )
            for clave in (
                "short",
                "name",
                "status",
                "state",
                "estado",
            )
        ).lower()

        jornada_aplazada = any(
            palabra in texto_jornada
            for palabra in (
                "aplaz",
                "postpon",
                "suspend",
            )
        )

        if not jornada_aplazada:

            for partido in games:

                if not isinstance(
                    partido,
                    dict,
                ):
                    continue

                texto_partido = " ".join(
                    str(partido.get(clave, ""))
                    for clave in (
                        "status",
                        "state",
                        "estado",
                    )
                ).lower()

                if any(
                    palabra in texto_partido
                    for palabra in (
                        "aplaz",
                        "postpon",
                        "suspend",
                    )
                ):
                    jornada_aplazada = True
                    break

        texto_boton = (
            f"⏳ {short}"
            if jornada_aplazada
            else str(short)
        )

        fila.append(
            InlineKeyboardButton(
                texto_boton,
                callback_data=(
                    f"jornada:{jornada_id}:todas"
                ),
            )
        )

        if len(fila) == 3:

            botones.append(
                fila
            )

            fila = []

    if fila:

        botones.append(
            fila
        )

    fila_paginacion = []

    if pagina > 0:

        fila_paginacion.append(
            InlineKeyboardButton(
                "◀️",
                callback_data=(
                    f"jornadas:pagina:"
                    f"{pagina - 1}"
                ),
            )
        )

    fila_paginacion.append(
        InlineKeyboardButton(
            f"{pagina + 1}/{total_paginas}",
            callback_data="noop",
        )
    )

    if pagina < total_paginas - 1:

        fila_paginacion.append(
            InlineKeyboardButton(
                "▶️",
                callback_data=(
                    f"jornadas:pagina:"
                    f"{pagina + 1}"
                ),
            )
        )

    botones.append(
        fila_paginacion
    )

    botones.append([
        InlineKeyboardButton(
            "◀️ Volver",
            callback_data=(
                "menu:jornadas"
            ),
        )
    ])

    return teclado_con_fijar(
        InlineKeyboardMarkup(
            botones
        )
    )


def formatear_dinero(valor):
    try:
        return f"{int(valor):,}€"
    except Exception:
        return "0€"


def formatear_fecha_boton(timestamp):
    if timestamp is None:
        return "??/??/??"

    try:
        from datetime import datetime

        fecha = datetime.fromtimestamp(
            float(timestamp),
            tz=MADRID_TZ,
        )

        return fecha.strftime(
            "%d/%m/%y"
        )

    except Exception:
        return "??/??/??"

async def mostrar_todas_jornadas(
    query,
    context,
    pagina=0,
):
    try:

        await editar_mensaje(
            query,
            (
                "⏳ CARGANDO JORNADAS...\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Consultando los datos de Biwenger..."
            ),
            None,
        )

        jornadas = obtener_jornadas()

        if not jornadas:

            await editar_mensaje(
                query,
                (
                    "📚 TODAS LAS JORNADAS\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "No se encontraron jornadas."
                ),
                teclado_submenu_jornadas(),
            )

            return

        jornadas = sorted(
            jornadas,
            key=lambda jornada: (
                min(
                    (
                        _timestamp_partido(game)
                        for game in jornada.get(
                            "games",
                            []
                        )
                        if _timestamp_partido(game)
                        is not None
                    ),
                    default=float("inf"),
                ),
                int(jornada.get("id", 0)),
            ),
        )

        texto = (
            "📚 TODAS LAS JORNADAS\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Selecciona una jornada:"
        )

        await editar_mensaje(
            query,
            texto,
            teclado_jornadas(
                jornadas,
                pagina,
            ),
        )

    except Exception as exc:

        logger.exception(
            "ERROR TODAS LAS JORNADAS: %s",
            exc,
        )

        await editar_mensaje(
            query,
            (
                "❌ No se pudieron cargar "
                "las jornadas."
            ),
            teclado_submenu_jornadas(),
        )


async def editar_mensaje(
    query,
    texto,
    reply_markup=None,
):
    try:
        await query.edit_message_text(
            texto,
            reply_markup=reply_markup,
        )

    except Exception as exc:
        if "Message is not modified" in str(exc):
            return

        raise


def guardar_mensaje_anterior(query, context):
    """
    Guarda el mensaje que se está sustituyendo para poder restaurarlo
    como un mensaje nuevo cuando el usuario fije la pantalla actual.
    """

    mensaje = query.message

    context.user_data[
        "mensaje_anterior_texto"
    ] = (
        mensaje.text or ""
    )

    context.user_data[
        "mensaje_anterior_markup"
    ] = (
        mensaje.reply_markup
    )


def teclado_con_fijar(reply_markup=None):
    """
    Añade el botón genérico de fijar a cualquier pantalla informativa.
    """

    filas = []

    if reply_markup is not None:

        try:

            filas = [
                list(fila)
                for fila in reply_markup.inline_keyboard
            ]

        except Exception:

            filas = []

    filas.append([
        InlineKeyboardButton(
            "📌 Fijar mensaje",
            callback_data="fijar_mensaje",
        )
    ])

    return InlineKeyboardMarkup(
        filas
    )


def _datos_boton_jugador(
    player_id,
    player_name=None,
    equipo=None,
    posicion=None,
):

    if player_id is None:

        return (
            player_name or "Jugador",
            equipo or "?",
            posicion or "?",
        )

    if equipo and posicion:

        return (
            player_name or "Jugador",
            equipo,
            posicion,
        )

    try:

        jugador = obtener_ficha_jugador(
            player_id
        )

    except Exception:

        jugador = None

    if isinstance(
        jugador,
        dict,
    ):

        return (
            player_name
            or jugador.get(
                "nombre",
                "Jugador",
            ),
            equipo
            or jugador.get(
                "equipo",
                "?",
            ),
            posicion
            or jugador.get(
                "posicion",
                "?",
            ),
        )

    return (
        player_name or "Jugador",
        equipo or "?",
        posicion or "?",
    )


def boton_jugador(
    player_id,
    player_name,
    equipo=None,
    posicion=None,
):

    if player_id is None:
        return None

    try:

        player_id = int(
            player_id
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    nombre, equipo, posicion = (
        _datos_boton_jugador(
            player_id,
            player_name,
            equipo,
            posicion,
        )
    )

    texto = (
        f"⚽ {nombre} "
        f"[{equipo}] "
        f"({posicion})"
    )

    return InlineKeyboardButton(
        texto,
        callback_data=(
            f"jugador:{player_id}"
        ),
    )


def boton_jugador_mercado(
    venta,
):

    player_id = venta.get(
        "player_id"
    )

    player_name = venta.get(
        "player_name",
        "Jugador",
    )

    equipo = venta.get(
        "team",
        "?",
    )

    posicion = venta.get(
        "position",
        "?",
    )

    return boton_jugador(
        player_id,
        player_name,
        equipo=equipo,
        posicion=posicion,
    )


def _pagina_jugadores(
    jugadores,
    pagina=0,
):
    if not isinstance(
        jugadores,
        list,
    ):
        jugadores = []

    total = len(jugadores)

    total_paginas = max(
        1,
        (
            total
            + JUGADORES_POR_PAGINA
            - 1
        )
        // JUGADORES_POR_PAGINA,
    )

    try:
        pagina = int(
            pagina
        )
    except (
        TypeError,
        ValueError,
    ):
        pagina = 0

    pagina = max(
        0,
        min(
            pagina,
            total_paginas - 1,
        ),
    )

    inicio = (
        pagina
        * JUGADORES_POR_PAGINA
    )

    fin = (
        inicio
        + JUGADORES_POR_PAGINA
    )

    return (
        jugadores[inicio:fin],
        pagina,
        total_paginas,
    )


def _botones_jugadores_paginados(
    jugadores,
    pagina,
    callback_base,
):
    jugadores_pagina, pagina, total_paginas = (
        _pagina_jugadores(
            jugadores,
            pagina,
        )
    )

    botones = []

    for jugador in jugadores_pagina:

        if not isinstance(
            jugador,
            dict,
        ):
            continue

        boton = boton_jugador(
            jugador.get(
                "player_id"
            ),
            jugador.get(
                "player_name",
                "Jugador",
            ),
            equipo=jugador.get(
                "team"
            ),
            posicion=jugador.get(
                "position"
            ),
        )

        if boton is not None:
            botones.append([
                boton
            ])

    fila_paginacion = []

    if pagina > 0:
        fila_paginacion.append(
            InlineKeyboardButton(
                "◀️",
                callback_data=(
                    f"{callback_base}:"
                    f"{pagina - 1}"
                ),
            )
        )

    fila_paginacion.append(
        InlineKeyboardButton(
            f"{pagina + 1}/{total_paginas}",
            callback_data="noop",
        )
    )

    if pagina < total_paginas - 1:
        fila_paginacion.append(
            InlineKeyboardButton(
                "▶️",
                callback_data=(
                    f"{callback_base}:"
                    f"{pagina + 1}"
                ),
            )
        )

    botones.append(
        fila_paginacion
    )

    return botones

async def noop_callback(
    update,
    context,
):
    await update.callback_query.answer()


def teclado_menu_liga():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Informe",
                callback_data="menu:informe",
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Mercado",
                callback_data="menu:mercado",
            )
        ],
        [
            InlineKeyboardButton(
                "📅 Jornadas",
                callback_data="menu:jornadas",
            )
        ],
        [
            InlineKeyboardButton(
                "🏆 Cambiar liga",
                callback_data="menu:liga",
            )
        ],
    ])


def texto_menu_liga(
    context,
):

    nombre = context.user_data.get(
        "liga_nombre",
        "Liga seleccionada",
    )

    return (
        f"🏆 {nombre}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Selecciona una opción:"
    )


async def mostrar_menu_liga(
    update,
    context,
):

    texto = texto_menu_liga(
        context
    )

    if update.message is not None:

        await update.message.reply_text(
            texto,
            reply_markup=teclado_menu_liga(),
        )

    elif update.callback_query is not None:

        await editar_mensaje(
            update.callback_query,
            texto,
            teclado_menu_liga(),
        )


def teclado_submenu_mercado():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔄 Mercado completo",
                callback_data="mercado:completo",
            )
        ],
        [
            InlineKeyboardButton(
                "📅 Mercado de hoy",
                callback_data="mercado:hoy",
            )
        ],
        [
            InlineKeyboardButton(
                "⏱️ Mercado 24h",
                callback_data="mercado:24h",
            )
        ],
        [
            InlineKeyboardButton(
                "🧑‍💼 Mercado por miembro",
                callback_data="mercado:miembro",
            )
        ],
        [
            InlineKeyboardButton(
                "◀️ Volver",
                callback_data="menu:principal",
            )
        ],
    ])


def teclado_submenu_jornadas():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟢 Jornada Actual",
                callback_data="jornadas:actual",
            )
        ],
        [
            InlineKeyboardButton(
                "📚 Todas las Jornadas",
                callback_data="jornadas:todas",
            )
        ],
        [
            InlineKeyboardButton(
                "◀️ Volver",
                callback_data="menu:principal",
            )
        ],
    ])


def texto_submenu_jornadas():
    return (
        "📅 JORNADAS\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Selecciona una opción:"
    )


async def mostrar_submenu_jornadas(
    update,
    context,
    editar=True,
):
    texto = texto_submenu_jornadas()

    teclado = teclado_submenu_jornadas()

    if update.callback_query is not None:

        if editar:

            await editar_mensaje(
                update.callback_query,
                texto,
                teclado,
            )

        else:

            await update.callback_query.message.reply_text(
                texto,
                reply_markup=teclado,
            )

        return

    if update.message is not None:

        await update.message.reply_text(
            texto,
            reply_markup=teclado,
        )


def teclado_mercado_hoy():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🤖 Jugadores en Venta - Sistema",
                callback_data="mercadohoy:sistema:TODAS",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Jugadores en Venta - Miembros",
                callback_data="mercadohoy:miembros:TODAS",
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Mis jugadores en venta",
                callback_data="mercadohoy:mios:TODAS",
            )
        ],
        [
            InlineKeyboardButton(
                "◀️ Volver a Mercado",
                callback_data="menu:mercado",
            )
        ],
    ])


def teclado_lista_mercado_hoy(
    tipo,
    posicion,
    mostrar_jugadores=False,
    pagina=0,
    total_jugadores=0,
):
    botones = []

    # ---------------------------------
    # MOSTRAR / OCULTAR JUGADORES
    # ---------------------------------

    if total_jugadores > 0:

        if mostrar_jugadores:
            botones.append([
                InlineKeyboardButton(
                    "🙈 Ocultar Jugadores",
                    callback_data=(
                        f"mercadohoy:"
                        f"{tipo}:"
                        f"{posicion}:"
                        f"ocultar"
                    ),
                )
            ])

        else:
            botones.append([
                InlineKeyboardButton(
                    "👤 Mostrar Jugadores",
                    callback_data=(
                        f"mercadohoy:"
                        f"{tipo}:"
                        f"{posicion}:"
                        f"mostrar:0"
                    ),
                )
            ])

    # ---------------------------------
    # POSICIONES
    # ---------------------------------

    fila_posiciones = []

    for codigo in POSICIONES_MERCADO_HOY_ORDEN:

        texto = (
            POSICIONES_MERCADO_HOY[
                codigo
            ]["boton"]
        )

        if posicion == codigo:
            texto += " ✅"

        fila_posiciones.append(
            InlineKeyboardButton(
                texto,
                callback_data=(
                    f"mercadohoy:"
                    f"{tipo}:"
                    f"{codigo}"
                ),
            )
        )

    botones.append(
        fila_posiciones
    )

    # ---------------------------------
    # TODAS LAS POSICIONES
    # ---------------------------------

    texto_todas = (
        "TODAS LAS POSICIONES"
    )

    if posicion == POSICION_TODAS:
        texto_todas += " ✅"

    botones.append([
        InlineKeyboardButton(
            texto_todas,
            callback_data=(
                f"mercadohoy:"
                f"{tipo}:"
                f"{POSICION_TODAS}"
            ),
        )
    ])

    # ---------------------------------
    # VOLVER
    # ---------------------------------

    botones.append([
        InlineKeyboardButton(
            "◀️ Volver al Mercado de Hoy",
            callback_data="mercado:hoy",
        )
    ])

    return teclado_con_fijar(
        InlineKeyboardMarkup(
            botones
        )
    )


def texto_mercado_hoy():

    return (
        "📅 MERCADO — HOY\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Selecciona qué jugadores quieres ver:"
    )


def texto_submenu_mercado():

    return (
        "🔄 MERCADO\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Selecciona una opción:"
    )


async def mostrar_submenu_mercado(
    update,
    context,
    editar=True,
):

    texto = texto_submenu_mercado()

    teclado = teclado_submenu_mercado()

    if update.callback_query is not None:

        if editar:

            await editar_mensaje(
                update.callback_query,
                texto,
                teclado,
            )

        else:

            await update.callback_query.message.reply_text(
                texto,
                reply_markup=teclado,
            )

        return

    if update.message is not None:

        await update.message.reply_text(
            texto,
            reply_markup=teclado,
        )


async def start(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )

    if liga_id:

        await mostrar_menu_liga(
            update,
            context,
        )

        return

    mensaje = await update.message.reply_text(
        "🤖 ConsultasBiwenger\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Primero selecciona una liga."
    )

    await mostrar_selector_liga(
        update,
        mensaje=mensaje,
    )


async def mostrar_selector_liga(
    update,
    mensaje=None,
):

    ligas = obtener_ligas()

    botones = []

    for liga in ligas:

        if not isinstance(
            liga,
            dict,
        ):
            continue

        liga_id = liga.get(
            "id"
        )

        nombre = liga.get(
            "name",
            f"Liga {liga_id}",
        )

        if liga_id is None:
            continue

        botones.append([
            InlineKeyboardButton(
                str(nombre),
                callback_data=(
                    f"liga:{liga_id}"
                ),
            )
        ])

    if not botones:

        if mensaje is not None:

            await mensaje.edit_text(
                "❌ No se encontraron ligas."
            )

        elif update.message is not None:

            await update.message.reply_text(
                "❌ No se encontraron ligas."
            )

        return

    markup = InlineKeyboardMarkup(
        botones
    )

    texto = (
        "🤖 ConsultasBiwenger\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Primero selecciona una liga."
    )

    if mensaje is not None:

        await mensaje.edit_text(
            texto,
            reply_markup=markup,
        )

        return

    if update.callback_query is not None:

        await editar_mensaje(
            update.callback_query,
            texto,
            markup,
        )

        return

    if update.message is not None:

        await update.message.reply_text(
            texto,
            reply_markup=markup,
        )


async def liga(
    update,
    context,
):

    try:

        await mostrar_selector_liga(
            update
        )

    except Exception as exc:

        logger.exception(
            "ERROR LIGA"
        )

        await update.message.reply_text(
            f"Error obteniendo ligas:\n{exc}"
        )


async def elegir_liga(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        if not query.data.startswith(
            "liga:"
        ):

            raise ValueError(
                "Callback de liga inválido"
            )

        liga_id = int(
            query.data.split(
                ":",
                1,
            )[1]
        )

        ligas = obtener_ligas()

        liga_encontrada = next(
            (
                liga
                for liga in ligas
                if (
                    isinstance(
                        liga,
                        dict,
                    )
                    and str(
                        liga.get("id")
                    )
                    == str(liga_id)
                )
            ),
            None,
        )

        if liga_encontrada is None:

            raise ValueError(
                "La liga seleccionada ya no está disponible."
            )

        liga_nombre = (
            liga_encontrada.get(
                "name",
                f"Liga {liga_id}",
            )
        )

        context.user_data[
            "liga"
        ] = liga_id

        context.user_data[
            "liga_nombre"
        ] = liga_nombre

        await editar_mensaje(
            query,
            texto_menu_liga(
                context
            ),
            teclado_menu_liga(),
        )

    except Exception:

        logger.exception(
            "ERROR ELEGIR LIGA"
        )

        await editar_mensaje(
            query,
            "❌ No se pudo seleccionar la liga.",
        )


async def comprobar_liga(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )

    if not liga_id:

        if update.message is not None:

            await update.message.reply_text(
                "Primero selecciona una liga con /liga"
            )

        elif update.callback_query is not None:

            await update.callback_query.answer(
                "Primero selecciona una liga.",
                show_alert=True,
            )

        return None

    return int(
        liga_id
    )


def construir_texto_informe(
    report,
):

    texto = (
        "📊 INFORME DE MANAGERS\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not report:

        texto += (
            "No se han encontrado miembros en esta liga."
        )

        return texto

    managers = sorted(
        report.items(),
        key=lambda item: item[1].get(
            "saldo_actual",
            0,
        ),
        reverse=True,
    )

    for manager, datos in managers:

        numero_jugadores = datos.get(
            "numero_jugadores",
            0,
        )

        compras = datos.get(
            "total_compras",
            0,
        )

        ventas = datos.get(
            "total_ventas",
            0,
        )

        saldo = datos.get(
            "saldo_actual",
            0,
        )

        puja_maxima = datos.get(
            "puja_maxima",
            0,
        )

        texto += (
            f"👤 {manager}\n"
            f"⚽ Jugadores: {numero_jugadores}\n"
            f"🟢 Compras: "
            f"{formatear_dinero(compras)}\n"
            f"🔴 Ventas: "
            f"{formatear_dinero(ventas)}\n"
            f"💰 Saldo: "
            f"{formatear_dinero(saldo)}\n"
            f"💵 Puja máxima: "
            f"{formatear_dinero(puja_maxima)}\n\n"
        )

    return texto.rstrip()


def teclado_volver_principal():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "◀️ Volver",
                callback_data="menu:principal",
            )
        ]
    ])


async def informe(
    update,
    context,
):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if not liga_id:
        return

    try:

        mensaje_carga = (
            await update.message.reply_text(
                "📊 Calculando informe..."
            )
        )

        report = obtener_informe(
            liga_id
        )

        texto = construir_texto_informe(
            report
        )

        botones = (
            teclado_con_fijar(
                teclado_volver_principal()
            )
        )

        if len(texto) <= MAX_TELEGRAM:

            await mensaje_carga.edit_text(
                texto,
                reply_markup=botones,
            )

        else:

            await mensaje_carga.delete()

            partes = [
                texto[
                    i:i + MAX_TELEGRAM
                ]
                for i in range(
                    0,
                    len(texto),
                    MAX_TELEGRAM,
                )
            ]

            for parte in partes[:-1]:

                await update.message.reply_text(
                    parte
                )

            await update.message.reply_text(
                partes[-1].rstrip(),
                reply_markup=botones,
            )

    except Exception as exc:

        logger.exception(
            "ERROR INFORME"
        )

        await update.message.reply_text(
            f"Error calculando informe:\n{exc}"
        )


async def enviar_movimientos(
    update,
    titulo,
    movimientos,
):

    if not movimientos:

        texto = (
            f"{titulo}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos."
        )

        if update.message is not None:

            return [
                await update.message.reply_text(
                    texto,
                    reply_markup=teclado_con_fijar(),
                )
            ]

        if update.callback_query is not None:

            return [
                await update.callback_query.message.reply_text(
                    texto,
                    reply_markup=teclado_con_fijar(),
                )
            ]

        return []

    texto_base = (
        f"{titulo}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    texto_actual = texto_base

    botones_actuales = []

    mensajes = []

    for movimiento in movimientos:

        texto_movimiento = movimiento.get(
            "texto",
            "",
        )

        boton = boton_jugador(
            movimiento.get(
                "player_id"
            ),
            movimiento.get(
                "player_name",
                "Jugador",
            ),
            equipo=movimiento.get(
                "team"
            ),
            posicion=movimiento.get(
                "position"
            ),
        )

        texto_candidato = (
            texto_actual
            + texto_movimiento
            + "\n\n"
        )

        if len(texto_candidato) > MAX_TELEGRAM:

            markup = (
                teclado_con_fijar(
                    InlineKeyboardMarkup(
                        botones_actuales
                    )
                )
                if botones_actuales
                else teclado_con_fijar()
            )

            if update.message is not None:

                mensaje = (
                    await update.message.reply_text(
                        texto_actual.rstrip(),
                        reply_markup=markup,
                    )
                )

            elif update.callback_query is not None:

                mensaje = (
                    await update.callback_query.message.reply_text(
                        texto_actual.rstrip(),
                        reply_markup=markup,
                    )
                )

            else:

                continue

            mensajes.append(
                mensaje
            )

            texto_actual = texto_base

            botones_actuales = []

        texto_actual += (
            texto_movimiento
            + "\n\n"
        )

        if boton is not None:

            botones_actuales.append([
                boton
            ])

    if texto_actual.strip():

        markup = (
            teclado_con_fijar(
                InlineKeyboardMarkup(
                    botones_actuales
                )
            )
            if botones_actuales
            else teclado_con_fijar()
        )

        if update.message is not None:

            mensaje = (
                await update.message.reply_text(
                    texto_actual.rstrip(),
                    reply_markup=markup,
                )
            )

        elif update.callback_query is not None:

            mensaje = (
                await update.callback_query.message.reply_text(
                    texto_actual.rstrip(),
                    reply_markup=markup,
                )
            )

        else:

            mensaje = None

        if mensaje is not None:

            mensajes.append(
                mensaje
            )

    return mensajes


async def enviar_mercado_hoy(
    update,
    datos,
):

    texto = texto_mercado_hoy()

    teclado = teclado_mercado_hoy()

    if update.callback_query is not None:

        await editar_mensaje(
            update.callback_query,
            texto,
            teclado,
        )

        return

    if update.message is not None:

        await update.message.reply_text(
            texto,
            reply_markup=teclado,
        )


def _normalizar_posicion(
    valor,
):

    if valor is None:
        return "?"

    texto = str(
        valor
    ).strip().upper()

    equivalencias = {
        "1": "PT",
        "GK": "PT",
        "POR": "PT",
        "PORTERO": "PT",
        "PT": "PT",

        "2": "DF",
        "DEF": "DF",
        "DEFENSA": "DF",
        "DF": "DF",

        "3": "MC",
        "MID": "MC",
        "MED": "MC",
        "MEDIO": "MC",
        "MC": "MC",

        "4": "DL",
        "FWD": "DL",
        "FW": "DL",
        "DEL": "DL",
        "DELANTERO": "DL",
        "DL": "DL",
    }

    return equivalencias.get(
        texto,
        texto
        if texto in {
            "PT",
            "DF",
            "MC",
            "DL",
        }
        else "?",
    )


def _posicion_venta(
    venta,
):

    sale = (
        venta.get("sale")
        if isinstance(
            venta,
            dict,
        )
        else None
    )

    if isinstance(
        sale,
        dict,
    ):

        player = sale.get(
            "player"
        )

        if isinstance(
            player,
            dict,
        ):

            for key in (
                "position",
                "pos",
                "positionName",
            ):

                if key in player:

                    posicion = _normalizar_posicion(
                        player.get(key)
                    )

                    if posicion != "?":
                        return posicion

        for key in (
            "position",
            "pos",
            "positionName",
        ):

            if key in sale:

                posicion = _normalizar_posicion(
                    sale.get(key)
                )

                if posicion != "?":
                    return posicion

    try:

        jugador = obtener_ficha_jugador(
            venta.get(
                "player_id"
            )
        )

    except Exception:

        jugador = None

    if isinstance(
        jugador,
        dict,
    ):

        datos = jugador.get(
            "datos"
        )

        if isinstance(
            datos,
            dict,
        ):

            for key in (
                "position",
                "pos",
                "positionName",
            ):

                if key in datos:

                    posicion = _normalizar_posicion(
                        datos.get(key)
                    )

                    if posicion != "?":
                        return posicion

    return "?"


def _orden_posicion(
    posicion,
):

    return {
        "DL": 0,
        "MC": 1,
        "DF": 2,
        "PT": 3,
    }.get(
        posicion,
        4,
    )


def _ordenar_ventas_por_posicion(
    ventas,
):

    enriquecidas = []

    for venta in ventas:

        posicion = _posicion_venta(
            venta
        )

        enriquecidas.append(
            (
                venta,
                posicion,
            )
        )

    enriquecidas.sort(
        key=lambda item: (
            _orden_posicion(
                item[1]
            ),
            str(
                item[0].get(
                    "player_name",
                    "",
                )
            ).casefold(),
        )
    )

    return enriquecidas

def _añadir_venta_mercado_hoy(
    lineas,
    venta,
    tipo,
):
    nombre = venta.get(
        "player_name",
        "Jugador desconocido",
    )

    equipo = venta.get(
        "team",
        "?",
    )

    puntos = venta.get(
        "points",
        0,
    )

    try:
        puntos = int(
            float(puntos)
        )
    except (
        TypeError,
        ValueError,
    ):
        puntos = 0

    precio = formatear_dinero(
        venta.get(
            "price",
            0,
        )
    )

    until_datetime = venta.get(
        "until_datetime"
    )

    # ---------------------------------
    # CABECERA DEL JUGADOR
    # ---------------------------------

    lineas.append(
        f"⚽ {nombre} [{equipo}]"
    )

    lineas.append(
        f"⭐ Puntos: {puntos}"
    )

    # ---------------------------------
    # MIS JUGADORES
    # ---------------------------------

    if tipo == "mios":

        valor_actual = venta.get(
            "market_value",
            0,
        )

        precio_compra = venta.get(
            "purchase_price"
        )

        # -----------------------------
        # PRECIOS
        # -----------------------------

        lineas.append(
            f"💰 Precio de Venta: {precio}"
        )

        if precio_compra is not None:

            lineas.append(
                "🛒 Precio de Compra: "
                + formatear_dinero(
                    precio_compra
                )
            )

        else:

            lineas.append(
                "🛒 Precio de Compra: "
                "No disponible"
            )

        lineas.append(
            "📊 Valor Actual: "
            + formatear_dinero(
                valor_actual
            )
        )

        # -----------------------------
        # DIFERENCIA DE VALOR
        # -----------------------------

        if precio_compra is not None:

            try:

                diferencia_valor = (
                    float(
                        valor_actual
                    )
                    - float(
                        precio_compra
                    )
                )

                if diferencia_valor > 0:

                    lineas.append(
                        "📈 Diferencia de Valor: +"
                        + formatear_dinero(
                            diferencia_valor
                        )
                    )

                elif diferencia_valor < 0:

                    lineas.append(
                        "📉 Diferencia de Valor: "
                        + formatear_dinero(
                            diferencia_valor
                        )
                    )

                else:

                    lineas.append(
                        "➖ Diferencia de Valor: 0€"
                    )

            except (
                TypeError,
                ValueError,
            ):
                pass

        # -----------------------------
        # OFERTAS
        # -----------------------------

        ofertas = venta.get(
            "offers_count",
            0,
        )

        lineas.append(
            f"💬 Ofertas recibidas: {ofertas}"
        )

        mejor_oferta = venta.get(
            "best_offer"
        )

        if mejor_oferta is not None:

            lineas.append(
                "🔥 Oferta más alta: "
                + formatear_dinero(
                    mejor_oferta
                )
            )

            # -------------------------
            # GANANCIA EN VENTA
            # -------------------------

            try:

                ganancia_venta = (
                    float(
                        mejor_oferta
                    )
                    - float(
                        valor_actual
                    )
                )

                if ganancia_venta > 0:

                    lineas.append(
                        "💵 Ganancia en Venta: +"
                        + formatear_dinero(
                            ganancia_venta
                        )
                    )

                elif ganancia_venta < 0:

                    lineas.append(
                        "💵 Ganancia en Venta: "
                        + formatear_dinero(
                            ganancia_venta
                        )
                    )

                else:

                    lineas.append(
                        "💵 Ganancia en Venta: 0€"
                    )

            except (
                TypeError,
                ValueError,
            ):
                pass

            # -------------------------
            # GANANCIA TOTAL
            # -------------------------

            if precio_compra is not None:

                try:

                    ganancia_total = (
                        float(
                            mejor_oferta
                        )
                        - float(
                            precio_compra
                        )
                    )

                    if ganancia_total > 0:

                        lineas.append(
                            "🏆 Ganancia Total: +"
                            + formatear_dinero(
                                ganancia_total
                            )
                        )

                    elif ganancia_total < 0:

                        lineas.append(
                            "🏆 Ganancia Total: "
                            + formatear_dinero(
                                ganancia_total
                            )
                        )

                    else:

                        lineas.append(
                            "🏆 Ganancia Total: 0€"
                        )

                except (
                    TypeError,
                    ValueError,
                ):
                    pass

    # ---------------------------------
    # SISTEMA / MIEMBROS
    # ---------------------------------

    else:

        lineas.append(
            f"💰 Precio: {precio}"
        )

        if (
            tipo == "miembros"
            and venta.get(
                "user_name"
            )
        ):

            lineas.append(
                "👤 Vendedor: "
                + str(
                    venta.get(
                        "user_name"
                    )
                )
            )

    # ---------------------------------
    # HORA DE EXPIRACIÓN
    #
    # NO SE MUESTRA PARA EL SISTEMA
    # ---------------------------------

    if (
        tipo != "sistema"
        and until_datetime is not None
    ):
        try:
            lineas.append(
                "⏳ Termina: "
                + until_datetime.strftime(
                    "%H:%M"
                )
            )
        except (
            AttributeError,
            TypeError,
        ):
            pass

    lineas.append("")


async def mostrar_lista_mercado_hoy(
    query,
    context,
    datos,
    tipo,
    posicion=POSICION_TODAS,
    mostrar_jugadores=False,
    pagina=0,
):
    if tipo == "sistema":

        titulo = (
            "🤖 JUGADORES EN VENTA — SISTEMA"
        )

        ventas = datos.get(
            "jugadores_sistema",
            [],
        )

    elif tipo == "miembros":

        titulo = (
            "👥 JUGADORES EN VENTA — MIEMBROS"
        )

        ventas = datos.get(
            "jugadores_managers",
            [],
        )

    elif tipo == "mios":

        titulo = (
            "👤 MIS JUGADORES EN VENTA"
        )

        ventas = datos.get(
            "jugadores_mios",
            [],
        )

    else:

        raise ValueError(
            "Tipo de mercado de hoy inválido"
        )

    if not isinstance(
        ventas,
        list,
    ):
        ventas = []

    ventas_filtradas = []

    for venta in ventas:

        venta_posicion = _posicion_venta(
            venta
        )

        if (
            posicion == POSICION_TODAS
            or venta_posicion == posicion
        ):
            ventas_filtradas.append(
                (
                    venta,
                    venta_posicion,
                )
            )

    def numero_venta(
        valor,
    ):
        try:
            return float(valor)
        except (
            TypeError,
            ValueError,
        ):
            return 0

    ventas_filtradas.sort(
        key=lambda item: (
            _orden_posicion(
                item[1]
            ),
            -numero_venta(
                item[0].get(
                    "points",
                    0,
                )
            ),
            -numero_venta(
                item[0].get(
                    "price",
                    0,
                )
            ),
            str(
                item[0].get(
                    "player_name",
                    "",
                )
            ).casefold(),
        )
    )

    ventas = [
        venta
        for venta, _ in ventas_filtradas
    ]

    lineas = [
        titulo,
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # ---------------------------------
    # TODAS LAS POSICIONES
    # ---------------------------------

    if posicion == POSICION_TODAS:

        if not ventas_filtradas:

            if tipo == "sistema":

                mensaje = (
                    "ℹ️ No hay jugadores del sistema "
                    "en venta actualmente."
                )

            elif tipo == "miembros":

                mensaje = (
                    "ℹ️ No hay jugadores de otros "
                    "miembros en venta actualmente."
                )

            else:

                mensaje = (
                    "ℹ️ No tienes jugadores en venta "
                    "actualmente."
                )

            lineas.append(
                mensaje
            )

        else:

            posicion_actual = None

            for venta, venta_posicion in (
                ventas_filtradas
            ):

                if (
                    venta_posicion
                    != posicion_actual
                ):

                    if (
                        posicion_actual
                        is not None
                    ):
                        lineas.append("")

                    datos_posicion = (
                        POSICIONES_MERCADO_HOY.get(
                            venta_posicion
                        )
                    )

                    if datos_posicion:

                        lineas.append(
                            datos_posicion[
                                "titulo"
                            ]
                        )

                    else:

                        lineas.append(
                            "📌 SIN POSICIÓN"
                        )

                    lineas.append("")

                    posicion_actual = (
                        venta_posicion
                    )

                _añadir_venta_mercado_hoy(
                    lineas,
                    venta,
                    tipo,
                )

    # ---------------------------------
    # UNA POSICIÓN CONCRETA
    # ---------------------------------

    else:

        datos_posicion = (
            POSICIONES_MERCADO_HOY.get(
                posicion
            )
        )

        if datos_posicion:

            lineas.append(
                datos_posicion[
                    "titulo"
                ]
            )

        lineas.append("")

        if not ventas_filtradas:

            lineas.append(
                "ℹ️ No hay ningún jugador en venta "
                "en esta posición."
            )

        else:

            for venta, _ in ventas_filtradas:

                _añadir_venta_mercado_hoy(
                    lineas,
                    venta,
                    tipo,
                )

    texto = "\n".join(
        lineas
    ).rstrip()

    if len(texto) > MAX_TELEGRAM:

        texto = (
            texto[
                :MAX_TELEGRAM - 30
            ].rstrip()
            + "\n\n…"
        )

    context.user_data[
        "mercado_hoy_jugadores"
    ] = ventas

    teclado_botones = (
        teclado_lista_mercado_hoy(
            tipo,
            posicion,
            mostrar_jugadores=mostrar_jugadores,
            pagina=pagina,
            total_jugadores=len(ventas),
        )
    )

    if mostrar_jugadores:

        botones_jugadores = (
            _botones_jugadores_paginados(
                ventas,
                pagina,
                (
                    "mercadohoy:"
                    f"{tipo}:"
                    f"{posicion}:mostrar"
                ),
            )
        )

        filas = [
            list(fila)
            for fila in (
                teclado_botones.inline_keyboard
            )
        ]

        # Insertar los jugadores justo después
        # del botón Mostrar/Ocultar.
        posicion_insercion = 1 if (
            len(filas) > 0
            and filas[0]
            and (
                "Mostrar Jugadores"
                in filas[0][0].text
                or "Ocultar Jugadores"
                in filas[0][0].text
            )
        ) else 0

        filas[
            posicion_insercion:
            posicion_insercion
        ] = botones_jugadores

        teclado_botones = teclado_con_fijar(
            InlineKeyboardMarkup(
                filas
            )
        )

    await editar_mensaje(
        query,
        texto,
        teclado_botones,
    )



async def enviar_submenu_mercado(
    update,
):

    if update.callback_query is not None:

        return await update.callback_query.message.reply_text(
            texto_submenu_mercado(),
            reply_markup=teclado_submenu_mercado(),
        )

    if update.message is not None:

        return await update.message.reply_text(
            texto_submenu_mercado(),
            reply_markup=teclado_submenu_mercado(),
        )

    return None


async def mercado(
    update,
    context,
):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if not liga_id:
        return

    try:

        datos = obtener_mercado_completo_datos(
            liga_id
        )

        context.user_data[
            "mercado_completo_datos"
        ] = datos

        texto = construir_mensaje_dia_mercado_completo(
            datos,
            0,
        )

        teclado = construir_botones_dia_mercado_completo(
            datos,
            0,
        )

        if update.callback_query is not None:

            await editar_mensaje(
                update.callback_query,
                texto,
                teclado,
            )

        elif update.message is not None:

            await update.message.reply_text(
                texto,
                reply_markup=teclado,
            )

    except Exception as exc:

        logger.exception(
            "ERROR MERCADO"
        )

        if update.callback_query is not None:

            await update.callback_query.message.reply_text(
                f"Error obteniendo mercado:\n{exc}"
            )

        elif update.message is not None:

            await update.message.reply_text(
                f"Error obteniendo mercado:\n{exc}"
            )


async def movimientos(
    update,
    context,
):

    await mercado(
        update,
        context,
    )


async def mercadohoy(
    update,
    context,
):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if not liga_id:
        return

    try:

        datos = obtener_mercado_hoy_datos(
            liga_id
        )

        await enviar_mercado_hoy(
            update,
            datos,
        )

    except Exception as exc:

        logger.exception(
            "ERROR MERCADO HOY"
        )

        if update.callback_query is not None:

            await update.callback_query.message.reply_text(
                f"Error obteniendo mercado de hoy:\n{exc}"
            )

        elif update.message is not None:

            await update.message.reply_text(
                f"Error obteniendo mercado de hoy:\n{exc}"
            )


async def mercado24(
    update,
    context,
):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if not liga_id:
        return

    try:

        datos = obtener_mercado_24h_datos(
            liga_id
        )

        ahora = datos[
            "fecha"
        ]

        movimientos_datos = datos[
            "movimientos"
        ]

        from biwenger import _nombre_fecha

        titulo = (
            "⏱️ MERCADO — 24H\n"
            "📅 "
            + _nombre_fecha(
                ahora.timestamp()
            )
        )

        if not movimientos_datos:

            texto = (
                titulo
                + "\n"
                + "━━━━━━━━━━━━━━━━━━━━\n\n"
                + "Sin movimientos."
            )

            if update.message is not None:

                await update.message.reply_text(
                    texto,
                    reply_markup=teclado_con_fijar(),
                )

            else:

                await update.callback_query.message.reply_text(
                    texto,
                    reply_markup=teclado_con_fijar(),
                )

        else:

            await enviar_movimientos(
                update,
                titulo,
                movimientos_datos,
            )

        await enviar_submenu_mercado(
            update
        )

    except Exception as exc:

        logger.exception(
            "ERROR MERCADO 24H"
        )

        if update.callback_query is not None:

            await update.callback_query.message.reply_text(
                f"Error obteniendo mercado 24h:\n{exc}"
            )

        elif update.message is not None:

            await update.message.reply_text(
                f"Error obteniendo mercado 24h:\n{exc}"
            )


def construir_mensaje_dia_miembro(
    nombre_miembro,
    grupos,
    orden,
    timestamps,
    indice,
):

    if not orden:

        return (
            f"🧑‍💼 MERCADO — {nombre_miembro}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos."
        )

    indice = max(
        0,
        min(
            indice,
            len(orden) - 1,
        ),
    )

    clave = orden[
        indice
    ]

    from biwenger import _nombre_fecha

    if clave == "desconocida":

        titulo_fecha = (
            "📅 FECHA DESCONOCIDA"
        )

    else:

        titulo_fecha = (
            "📅 "
            + _nombre_fecha(
                timestamps.get(
                    clave
                )
            )
        )

    movimientos = grupos.get(
        clave,
        [],
    )

    lineas = [
        f"🧑‍💼 MERCADO — {nombre_miembro}",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        titulo_fecha,
        "",
    ]

    if movimientos:

        for movimiento in movimientos:

            lineas.append(
                movimiento.get(
                    "texto",
                    "",
                )
            )

            lineas.append("")

    else:

        lineas.append(
            "Sin movimientos."
        )

    return "\n".join(
        lineas
    ).rstrip()

def construir_botones_dias(
    liga_id,
    miembro_id,
    indice,
    orden,
    timestamps,
    movimientos,
    mostrar_jugadores,
    pagina_jugadores,
):

    botones = []

    if movimientos:

        botones.append([
            InlineKeyboardButton(
                (
                    "🙈 Ocultar Jugadores"
                    if mostrar_jugadores
                    else "👤 Mostrar Jugadores"
                ),
                callback_data=(
                    f"miembrodia:"
                    f"{liga_id}:"
                    f"{miembro_id}:"
                    f"{indice}:"
                    f"{'ocultar' if mostrar_jugadores else 'mostrar'}:"
                    f"{pagina_jugadores}"
                ),
            )
        ])

        if mostrar_jugadores:

            botones.extend(
                _botones_jugadores_paginados(
                    movimientos,
                    pagina_jugadores,
                    (
                        f"miembrodia:"
                        f"{liga_id}:"
                        f"{miembro_id}:"
                        f"{indice}:"
                        "mostrar"
                    ),
                )
            )

    fila_fechas = []

    if indice > 0:

        indice_anterior = (
            indice - 1
        )

        clave_anterior = (
            orden[
                indice_anterior
            ]
        )

        fecha_anterior = (
            formatear_fecha_boton(
                timestamps.get(
                    clave_anterior
                )
            )
        )

        fila_fechas.append(
            InlineKeyboardButton(
                f"◀️ {fecha_anterior}",
                callback_data=(
                    f"miembrodia:"
                    f"{liga_id}:"
                    f"{miembro_id}:"
                    f"{indice_anterior}"
                ),
            )
        )

    if indice < len(orden) - 1:

        indice_siguiente = (
            indice + 1
        )

        clave_siguiente = (
            orden[
                indice_siguiente
            ]
        )

        fecha_siguiente = (
            formatear_fecha_boton(
                timestamps.get(
                    clave_siguiente
                )
            )
        )

        fila_fechas.append(
            InlineKeyboardButton(
                f"{fecha_siguiente} ▶️",
                callback_data=(
                    f"miembrodia:"
                    f"{liga_id}:"
                    f"{miembro_id}:"
                    f"{indice_siguiente}"
                ),
            )
        )

    if fila_fechas:

        botones.append(
            fila_fechas
        )

    botones.append([
        InlineKeyboardButton(
            "👥 Cambiar miembro",
            callback_data=(
                f"miembros:{liga_id}"
            ),
        )
    ])

    botones.append([
        InlineKeyboardButton(
            "◀️ Volver a Mercado",
            callback_data=(
                "menu:mercado"
            ),
        )
    ])

    return teclado_con_fijar(
        InlineKeyboardMarkup(
            botones
        )
    )


async def mostrar_dia_miembro(
    query,
    context,
    liga_id,
    miembro_id,
    indice,
    datos=None,
    mostrar_jugadores=False,
    pagina_jugadores=0,
):

    try:

        if datos is None:

            datos = (
                obtener_mercado_miembro_datos(
                    liga_id,
                    miembro_id,
                )
            )

        if "error" in datos:

            await editar_mensaje(
                query,
                datos["error"],
            )

            return

        nombre_miembro = datos.get(
            "nombre_miembro",
            "Desconocido",
        )

        grupos = datos.get(
            "grupos",
            {},
        )

        orden = datos.get(
            "orden",
            [],
        )

        timestamps = datos.get(
            "timestamps",
            {},
        )

        if not orden:

            guardar_mensaje_anterior(
                query,
                context,
            )

            await editar_mensaje(
                query,
                (
                    f"🧑‍💼 MERCADO — {nombre_miembro}\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Sin movimientos."
                ),
                teclado_con_fijar(
                    InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "👥 Cambiar miembro",
                                callback_data=(
                                    f"miembros:{liga_id}"
                                ),
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "◀️ Volver a Mercado",
                                callback_data=(
                                    "menu:mercado"
                                ),
                            )
                        ],
                    ])
                ),
            )

            return

        indice = max(
            0,
            min(
                indice,
                len(orden) - 1,
            ),
        )

        clave = orden[
            indice
        ]

        movimientos = grupos.get(
            clave,
            [],
        )

        texto = (
            construir_mensaje_dia_miembro(
                nombre_miembro,
                grupos,
                orden,
                timestamps,
                indice,
            )
        )

        if len(texto) > MAX_TELEGRAM:

            texto = (
                texto[
                    :MAX_TELEGRAM - 50
                ]
                + "\n\n…"
            )

        teclado = (
            construir_botones_dias(
                liga_id,
                miembro_id,
                indice,
                orden,
                timestamps,
                movimientos,
                mostrar_jugadores,
                pagina_jugadores,
            )
        )

        guardar_mensaje_anterior(
            query,
            context,
        )

        await editar_mensaje(
            query,
            texto,
            teclado,
        )

    except Exception:

        logger.exception(
            "ERROR MOSTRAR DÍA MIEMBRO"
        )

        await editar_mensaje(
            query,
            "❌ No se pudieron obtener los movimientos del miembro.",
        )


async def mercadomiembro(
    update,
    context,
):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if not liga_id:
        return

    try:

        miembros = obtener_miembros_liga(
            liga_id
        )

        if not miembros:

            await update.message.reply_text(
                "❌ No se encontraron miembros en esta liga."
            )

            return

        botones = []

        for miembro in miembros:

            miembro_id = miembro.get(
                "id"
            )

            nombre = miembro.get(
                "nombre",
                "Desconocido",
            )

            if miembro_id is None:
                continue

            botones.append([
                InlineKeyboardButton(
                    str(nombre),
                    callback_data=(
                        f"miembro:"
                        f"{liga_id}:"
                        f"{miembro_id}"
                    ),
                )
            ])

        if not botones:

            await update.message.reply_text(
                "❌ No se pudieron cargar los miembros."
            )

            return

        await update.message.reply_text(
            "🧑‍💼 Selecciona un miembro:",
            reply_markup=InlineKeyboardMarkup(
                botones
            ),
        )

    except Exception as exc:

        logger.exception(
            "ERROR MERCADO POR MIEMBRO"
        )

        await update.message.reply_text(
            f"Error obteniendo miembros:\n{exc}"
        )


async def mostrar_selector_miembros(
    query,
    liga_id,
):

    try:

        miembros = obtener_miembros_liga(
            liga_id
        )

        botones = []

        for miembro in miembros:

            miembro_id = miembro.get(
                "id"
            )

            nombre = miembro.get(
                "nombre",
                "Desconocido",
            )

            if miembro_id is None:
                continue

            botones.append([
                InlineKeyboardButton(
                    str(nombre),
                    callback_data=(
                        f"miembro:"
                        f"{liga_id}:"
                        f"{miembro_id}"
                    ),
                )
            ])

        if not botones:

            await editar_mensaje(
                query,
                "❌ No se encontraron miembros.",
            )

            return

        botones.append([
            InlineKeyboardButton(
                "◀️ Volver a Mercado",
                callback_data=(
                    "menu:mercado"
                ),
            )
        ])

        await editar_mensaje(
            query,
            "🧑‍💼 Selecciona un miembro:",
            InlineKeyboardMarkup(
                botones
            ),
        )

    except Exception:

        logger.exception(
            "ERROR MOSTRAR SELECTOR MIEMBROS"
        )

        await editar_mensaje(
            query,
            "❌ No se pudieron cargar los miembros.",
        )


async def elegir_miembro(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        partes = query.data.split(
            ":"
        )

        if len(partes) != 3:

            raise ValueError(
                "Callback de miembro inválido"
            )

        liga_id = int(
            partes[1]
        )

        miembro_id = int(
            partes[2]
        )

        liga_actual = (
            context.user_data.get(
                "liga"
            )
        )

        if (
            liga_actual is None
            or int(liga_actual)
            != liga_id
        ):

            raise ValueError(
                "La liga seleccionada ya no coincide."
            )

        datos = (
            obtener_mercado_miembro_datos(
                liga_id,
                miembro_id,
            )
        )

        await mostrar_dia_miembro(
            query,
            context,
            liga_id,
            miembro_id,
            0,
            datos,
        )

    except Exception:

        logger.exception(
            "ERROR ELEGIR MIEMBRO"
        )

        await editar_mensaje(
            query,
            "❌ No se pudieron obtener los movimientos del miembro.",
        )


async def cambiar_dia_miembro(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        partes = query.data.split(
            ":"
        )

        if len(partes) < 4:

            raise ValueError(
                "Callback de día inválido"
            )

        liga_id = int(
            partes[1]
        )

        miembro_id = int(
            partes[2]
        )

        indice = int(
            partes[3]
        )

        mostrar_jugadores = False
        pagina_jugadores = 0

        if len(partes) >= 5:

            accion = partes[4]

            if accion == "mostrar":
                mostrar_jugadores = True

                if len(partes) >= 6:
                    pagina_jugadores = int(
                        partes[5]
                    )

            elif accion == "ocultar":
                mostrar_jugadores = False

        liga_actual = (
            context.user_data.get(
                "liga"
            )
        )

        if (
            liga_actual is None
            or int(liga_actual)
            != liga_id
        ):

            raise ValueError(
                "La liga seleccionada ya no coincide."
            )

        await mostrar_dia_miembro(
            query,
            context,
            liga_id,
            miembro_id,
            indice,
            mostrar_jugadores=mostrar_jugadores,
            pagina_jugadores=pagina_jugadores,
        )

    except Exception:

        logger.exception(
            "ERROR CAMBIAR DÍA MIEMBRO"
        )

        await editar_mensaje(
            query,
            "❌ No se pudo cambiar de día.",
        )


async def volver_miembros(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        partes = query.data.split(
            ":"
        )

        if len(partes) != 2:

            raise ValueError(
                "Callback de miembros inválido"
            )

        liga_id = int(
            partes[1]
        )

        liga_actual = (
            context.user_data.get(
                "liga"
            )
        )

        if (
            liga_actual is None
            or int(liga_actual)
            != liga_id
        ):

            raise ValueError(
                "La liga seleccionada ya no coincide."
            )

        await mostrar_selector_miembros(
            query,
            liga_id,
        )

    except Exception:

        logger.exception(
            "ERROR VOLVER MIEMBROS"
        )

        await editar_mensaje(
            query,
            "❌ No se pudo volver a la selección de miembros.",
        )


def construir_texto_jornada(
    jornada,
    origen="actual",
):
    short = jornada.get(
        "short",
        "J?",
    )

    name = jornada.get(
        "name",
        "",
    )

    if "aplazada" in name.lower():
        texto_boton = f"{short} ⏳"
    else:
        texto_boton = str(short)

    games = jornada.get(
        "games",
        [],
    )

    indicador_aplazada = ""

    if "aplazada" in str(name).lower():
        indicador_aplazada = " ⏳"

    numero_jornada = short

    if short.upper().startswith("J"):
        numero_jornada = short[1:]

    if origen == "actual":

        lineas = [
            "📅 JORNADA ACTUAL",
            "━━━━━━━━━━━━━━━━━━━━",
        ]

    else:

        lineas = [
            f"🏆 Jornada {numero_jornada}{indicador_aplazada}",
            "━━━━━━━━━━━━━━━━━━━━",
        ]

    if name:

        lineas.append(
            name
        )

    hora_inicio = None

    for partido in games:

        if not isinstance(
            partido,
            dict,
        ):
            continue

        timestamp = _timestamp_partido(
            partido
        )

        if timestamp is not None:

            hora_inicio = datetime.fromtimestamp(
                timestamp,
                tz=MADRID_TZ,
            )

            break

    if hora_inicio is not None:

        traducciones_dia = {
            "Monday": "Lunes",
            "Tuesday": "Martes",
            "Wednesday": "Miércoles",
            "Thursday": "Jueves",
            "Friday": "Viernes",
            "Saturday": "Sábado",
            "Sunday": "Domingo",
        }

        dia_ingles = hora_inicio.strftime(
            "%A"
        )

        dia = traducciones_dia.get(
            dia_ingles,
            dia_ingles,
        )

        lineas.append(
            "🕐 Inicio: "
            f"{dia} "
            f"{hora_inicio.strftime('%d/%m')}"
            f" · "
            f"{hora_inicio.strftime('%H:%M')}"
        )

    else:

        lineas.append(
            "🕐 Inicio: Pendiente"
        )

    lineas.append("")

    if not games:

        lineas.append(
            "No hay partidos disponibles."
        )

        return "\n".join(
            lineas
        )

    lineas.append(
        "⚽ PARTIDOS"
    )

    lineas.append("")

    for partido in games:

        if not isinstance(
            partido,
            dict,
        ):
            continue

        home = partido.get(
            "home",
            "Local",
        )

        away = partido.get(
            "away",
            "Visitante",
        )

        local_score, visitante_score, status = _resultado_partido(partido)

        if local_score is not None and visitante_score is not None:
            marcador = f"  {local_score}-{visitante_score}"
        else:
            marcador = ""

        if status:
            estado = str(status).strip().lower()

            if estado in ("finished", "finishedgame", "finalizado", "ended"):
                estado_texto = " ✅"
            elif estado in ("started", "live", "playing", "inprogress", "en juego"):
                estado_texto = " 🔴 EN DIRECTO"
            else:
                estado_texto = ""
        else:
            estado_texto = ""

        if isinstance(
            home,
            dict,
        ):

            home = (
                home.get("name")
                or home.get("shortName")
                or home.get("id")
                or "Local"
            )

        if isinstance(
            away,
            dict,
        ):

            away = (
                away.get("name")
                or away.get("shortName")
                or away.get("id")
                or "Visitante"
            )

        timestamp = _timestamp_partido(
            partido
        )

        if timestamp is not None:

            fecha_partido = datetime.fromtimestamp(
                timestamp,
                tz=MADRID_TZ,
            )

            traducciones_dia = {
                "Mon": "Lun",
                "Tue": "Mar",
                "Wed": "Mié",
                "Thu": "Jue",
                "Fri": "Vie",
                "Sat": "Sáb",
                "Sun": "Dom",
            }

            dia_ingles = fecha_partido.strftime(
                "%a"
            )

            dia = traducciones_dia.get(
                dia_ingles,
                dia_ingles,
            )

            texto_fecha = (
                f"{dia} "
                f"{fecha_partido.strftime('%d/%m')}"
                f" · "
                f"{fecha_partido.strftime('%H:%M')}"
            )

            lineas.append(
                f"🕐 {texto_fecha}"
            )

        else:

            lineas.append(
                "🕐 Fecha pendiente"
            )

        lineas.append(
            f"⚽ {home} — {away}{marcador}{estado_texto}",
        )

        if local_score is not None and visitante_score is not None:

            if status:

                estado_normalizado = (
                    str(status)
                    .strip()
                    .lower()
                )

            else:

                estado_normalizado = ""

            if estado_normalizado in (
                "finished",
                "finishedgame",
                "finalizado",
                "ended",
                "completed",
            ):

                lineas.append(
                    "✅ Finalizado"
                )

            elif estado_normalizado in (
                "started",
                "live",
                "playing",
                "inprogress",
                "in_progress",
                "en juego",
            ):

                lineas.append(
                    "🔴 En directo"
                )

            else:

                lineas.append(
                    "📊 Resultado"
                )

        else:

            lineas.append(
                "⏳ Pendiente"
            )
        lineas.append("")

    return "\n".join(
        lineas
    ).rstrip()

def teclado_jornada(
    jornada_id,
    origen="actual",
):
    """
    Teclado de una jornada concreta.
    """

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚽ Partidos",
                callback_data=(
                    f"jornada:partidos:{jornada_id}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Onces elegidos",
                callback_data=(
                    f"jornada:onces:{jornada_id}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Mi jornada",
                callback_data=(
                    f"jornada:mi_jornada:{jornada_id}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Volver a Jornadas",
                callback_data="menu:jornadas",
            )
        ],
    ])

    return teclado_con_fijar(
        teclado
    )


def construir_texto_ficha_jugador(
    jugador,
):

    nombre = jugador.get(
        "nombre",
        "Desconocido",
    )

    posicion = jugador.get(
        "posicion",
        "?",
    )

    equipo = jugador.get(
        "equipo",
        "?",
    )

    equipo_nombre = jugador.get(
        "equipo_nombre",
        "Desconocido",
    )

    posicion_nombre = jugador.get(
        "posicion_nombre",
        "Posición desconocida",
    )

    propietario = jugador.get(
        "propietario",
        "No disponible",
    )

    precio = jugador.get(
        "precio",
        0,
    )

    puntos = jugador.get(
        "puntos",
        0,
    )

    ultimo = jugador.get(
        "puntos_ultima_jornada",
        0,
    )

    media = jugador.get(
        "media_puntos",
        0,
    )

    titulo = (
        f"⚽ {nombre} "
        f"[{equipo}] "
        f"({posicion})"
    )

    return (
        f"{titulo}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Nombre: {nombre}\n"
        f"🏟️ Equipo: {equipo_nombre}\n"
        f"📍 Posición: {posicion_nombre}\n"
        f"💰 Valor actual: "
        f"{formatear_dinero(precio)}\n"
        f"👤 Propietario: {propietario}\n"
        f"⭐ Puntos totales: {puntos}\n"
        f"📅 Puntos última jornada: {ultimo}\n"
        f"📊 Media de puntos: {media}\n"
    )


def teclado_ficha_jugador(
    player_id,
    fijada=False,
):

    if fijada:
        return None

    return teclado_con_fijar(
        InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "◀️ Anterior",
                    callback_data="jugador_anterior",
                )
            ]
        ])
    )


async def ficha_jugador(
    update,
    context,
):

    query = update.callback_query

    try:

        if not query.data.startswith(
            "jugador:"
        ):

            raise ValueError(
                "Callback de jugador inválido"
            )

        player_id = int(
            query.data.split(
                ":",
                1,
            )[1]
        )

        jugador = obtener_ficha_jugador(
            player_id
        )

        if not jugador:

            await query.answer(
                "❌ No se encontró la ficha del jugador.",
                show_alert=True,
            )

            return

        guardar_mensaje_anterior(
            query,
            context,
        )

        texto = (
            construir_texto_ficha_jugador(
                jugador
            )
        )

        await query.answer()

        await editar_mensaje(
            query,
            texto,
            teclado_ficha_jugador(
                player_id
            ),
        )

    except Exception:

        logger.exception(
            "ERROR FICHA JUGADOR"
        )

        try:

            await query.answer(
                "❌ No se pudo obtener la ficha del jugador.",
                show_alert=True,
            )

        except Exception:
            pass


async def fijar_mensaje(
    update,
    context,
):

    """
    Fija la pantalla actual como mensaje y devuelve debajo
    directamente el mensaje anterior.
    """

    query = update.callback_query

    try:

        await query.answer(
            "Mensaje fijado"
        )

        texto_actual = (
            query.message.text or ""
        )

        await editar_mensaje(
            query,
            texto_actual,
            None,
        )

        texto_anterior = (
            context.user_data.get(
                "mensaje_anterior_texto"
            )
        )

        markup_anterior = (
            context.user_data.get(
                "mensaje_anterior_markup"
            )
        )

        if texto_anterior:

            await query.message.reply_text(
                texto_anterior,
                reply_markup=markup_anterior,
            )

    except Exception:

        logger.exception(
            "ERROR FIJAR MENSAJE"
        )

        try:

            await query.answer(
                "❌ No se pudo fijar el mensaje.",
                show_alert=True,
            )

        except Exception:
            pass


async def fijar_jugador(
    update,
    context,
):

    """
    Compatibilidad para el antiguo botón de fijar jugador.

    Al fijar una ficha, la ficha actual queda como mensaje
    independiente y debajo se recupera directamente la
    pantalla anterior.
    """

    query = update.callback_query

    try:

        await query.answer(
            "Jugador fijado"
        )

        texto_ficha = (
            query.message.text or ""
        )

        await editar_mensaje(
            query,
            texto_ficha,
            None,
        )

        texto_anterior = (
            context.user_data.get(
                "mensaje_anterior_texto"
            )
        )

        markup_anterior = (
            context.user_data.get(
                "mensaje_anterior_markup"
            )
        )

        if texto_anterior:

            await query.message.reply_text(
                texto_anterior,
                reply_markup=markup_anterior,
            )

    except Exception:

        logger.exception(
            "ERROR FIJAR JUGADOR"
        )

        try:

            await query.answer(
                "❌ No se pudo fijar la ficha.",
                show_alert=True,
            )

        except Exception:
            pass


async def volver_desde_jugador(
    update,
    context,
):

    query = update.callback_query

    try:

        await query.answer()

        texto = (
            context.user_data.get(
                "mensaje_anterior_texto"
            )
        )

        markup = (
            context.user_data.get(
                "mensaje_anterior_markup"
            )
        )

        if texto:

            await editar_mensaje(
                query,
                texto,
                markup,
            )

        else:

            await editar_mensaje(
                query,
                texto_menu_liga(
                    context
                ),
                teclado_menu_liga(),
            )

    except Exception:

        logger.exception(
            "ERROR VOLVER DESDE JUGADOR"
        )

        await editar_mensaje(
            query,
            texto_menu_liga(
                context
            ),
            teclado_menu_liga(),
        )


async def ayuda(
    update,
    context,
):

    texto = (
        "📚 AYUDA\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 Informe\n"
        "Información de managers, jugadores, compras, ventas, saldo y puja máxima.\n\n"
        "🔄 Mercado\n"
        "Mercado completo, mercado de hoy, mercado 24h y mercado por miembro.\n\n"
        "📅 Mercado de hoy\n"
        "Muestra los jugadores actualmente disponibles en el mercado de Biwenger.\n\n"
        "⏱️ Mercado 24h\n"
        "Muestra los movimientos de las últimas 24 horas.\n\n"
        "🏆 Liga\n"
        "Cambiar de liga.\n\n"
        "También puedes utilizar los botones de los menús para navegar."
    )

    await update.message.reply_text(
        texto
    )


async def menu_callback(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        accion = query.data.split(
            ":",
            1,
        )[1]

        if accion == "informe":

            liga_id = (
                context.user_data.get(
                    "liga"
                )
            )

            if not liga_id:

                await query.answer(
                    "Primero selecciona una liga.",
                    show_alert=True,
                )

                return

            report = obtener_informe(
                int(liga_id)
            )

            texto = construir_texto_informe(
                report
            )

            if len(texto) <= MAX_TELEGRAM:

                guardar_mensaje_anterior(
                    query,
                    context,
                )

                await editar_mensaje(
                    query,
                    texto,
                    teclado_con_fijar(
                        teclado_volver_principal()
                    ),
                )

            else:

                await editar_mensaje(
                    query,
                    (
                        "📊 INFORME DE MANAGERS\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "El informe es demasiado largo "
                        "para mostrarse en una sola pantalla."
                    ),
                )

                partes = [
                    texto[
                        i:i + MAX_TELEGRAM
                    ]
                    for i in range(
                        0,
                        len(texto),
                        MAX_TELEGRAM,
                    )
                ]

                for parte in partes:

                    await query.message.reply_text(
                        parte
                    )

                await query.message.reply_text(
                    "📊 INFORME\n"
                    "━━━━━━━━━━━━━━━━━━━━",
                    reply_markup=(
                        teclado_volver_principal()
                    ),
                )

        elif accion == "mercado":

            await mostrar_submenu_mercado(
                update,
                context,
                editar=True,
            )

        elif accion == "jornadas":

            await mostrar_submenu_jornadas(
                update,
                context,
                editar=True,
            )

        elif accion == "principal":

            await editar_mensaje(
                query,
                texto_menu_liga(
                    context
                ),
                teclado_menu_liga(),
            )

        elif accion == "liga":

            await mostrar_selector_liga(
                update
            )

    except Exception:

        logger.exception(
            "ERROR MENU CALLBACK"
        )

        try:

            await query.answer(
                "❌ Se produjo un error.",
                show_alert=True,
            )

        except Exception:
            pass


def construir_mensaje_dia_mercado_completo(
    datos,
    indice,
):

    grupos = datos.get(
        "grupos",
        {},
    )

    orden = datos.get(
        "orden",
        [],
    )

    timestamps = datos.get(
        "timestamps",
        {},
    )

    if not orden:

        return (
            "🔄 MERCADO COMPLETO\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos."
        )

    indice = max(
        0,
        min(
            indice,
            len(orden) - 1,
        ),
    )

    clave = orden[
        indice
    ]

    from biwenger import _nombre_fecha

    titulo = (
        "📅 FECHA DESCONOCIDA"
        if clave == "desconocida"
        else (
            "📅 "
            + _nombre_fecha(
                timestamps.get(
                    clave
                )
            )
        )
    )

    movimientos = grupos.get(
        clave,
        [],
    )

    lineas = [
        "🔄 MERCADO COMPLETO",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        titulo,
        "",
    ]

    if movimientos:

        for movimiento in movimientos:

            lineas.append(
                movimiento.get(
                    "texto",
                    "",
                )
            )

            lineas.append("")

    else:

        lineas.append(
            "Sin movimientos."
        )

    return "\n".join(
        lineas
    ).rstrip()

def construir_botones_jugadores_mercado_completo(
    movimientos,
    indice,
    pagina=0,
):
    jugadores = []

    for movimiento in movimientos:

        if not isinstance(
            movimiento,
            dict,
        ):
            continue

        jugadores.append(
            movimiento
        )

    return _botones_jugadores_paginados(
        jugadores,
        pagina,
        f"completodia:jugadores:{indice}:mostrar",
    )

def construir_botones_dia_mercado_completo(
    datos,
    indice,
    mostrar_jugadores=False,
    pagina_jugadores=0,
):

    orden = datos.get(
        "orden",
        [],
    )

    timestamps = datos.get(
        "timestamps",
        {},
    )

    grupos = datos.get(
        "grupos",
        {},
    )

    if not orden:

        return teclado_con_fijar(
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "◀️ Volver a Mercado",
                        callback_data=(
                            "menu:mercado"
                        ),
                    )
                ]
            ])
        )

    indice = max(
        0,
        min(
            indice,
            len(orden) - 1,
        ),
    )

    botones = []

    movimientos = grupos.get(
        orden[indice],
        [],
    )

    if movimientos:

        botones.append([
            InlineKeyboardButton(
                (
                    "🙈 Ocultar Jugadores"
                    if mostrar_jugadores
                    else "👤 Mostrar Jugadores"
                ),
                callback_data=(
                    f"completodia:"
                    f"jugadores:"
                    f"{indice}:"
                    f"{'ocultar' if mostrar_jugadores else 'mostrar'}:"
                    f"{pagina_jugadores}"
                ),
            )
        ])

        if mostrar_jugadores:

            botones.extend(
                construir_botones_jugadores_mercado_completo(
                    movimientos,
                    pagina_jugadores,
                )
            )

    fila = []

    if indice > 0:

        anterior = (
            formatear_fecha_boton(
                timestamps.get(
                    orden[
                        indice - 1
                    ]
                )
            )
        )

        fila.append(
            InlineKeyboardButton(
                f"◀️ {anterior}",
                callback_data=(
                    f"completodia:"
                    f"{indice - 1}"
                ),
            )
        )

    if indice < len(orden) - 1:

        siguiente = (
            formatear_fecha_boton(
                timestamps.get(
                    orden[
                        indice + 1
                    ]
                )
            )
        )

        fila.append(
            InlineKeyboardButton(
                f"{siguiente} ▶️",
                callback_data=(
                    f"completodia:"
                    f"{indice + 1}"
                ),
            )
        )

    if fila:

        botones.append(
            fila
        )

    botones.append([
        InlineKeyboardButton(
            "◀️ Volver a Mercado",
            callback_data=(
                "menu:mercado"
            ),
        )
    ])

    return teclado_con_fijar(
        InlineKeyboardMarkup(
            botones
        )
    )


async def mostrar_dia_mercado_completo(
    query,
    context,
    indice,
    datos=None,
    mostrar_jugadores=False,
    pagina_jugadores=0,
):

    if datos is None:

        datos = context.user_data.get(
            "mercado_completo_datos"
        )

    if not datos:

        liga_id = (
            context.user_data.get(
                "liga"
            )
        )

        datos = (
            obtener_mercado_completo_datos(
                int(liga_id)
            )
        )

        context.user_data[
            "mercado_completo_datos"
        ] = datos

    texto = (
        construir_mensaje_dia_mercado_completo(
            datos,
            indice,
        )
    )

    teclado = (
        construir_botones_dia_mercado_completo(
            datos,
            indice,
            mostrar_jugadores,
            pagina_jugadores,
        )
    )

    guardar_mensaje_anterior(
        query,
        context,
    )

    await editar_mensaje(
        query,
        texto,
        teclado,
    )


async def cambiar_dia_mercado_completo(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        partes = query.data.split(":")

        if len(partes) >= 3 and partes[1] == "jugadores":

            indice = int(
                partes[2]
            )

            accion = (
                partes[3]
                if len(partes) >= 4
                else "mostrar"
            )

            pagina = (
                int(partes[4])
                if len(partes) >= 5
                else 0
            )

            mostrar_jugadores = (
                accion == "mostrar"
            )

            await mostrar_dia_mercado_completo(
                query,
                context,
                indice,
                mostrar_jugadores=mostrar_jugadores,
                pagina_jugadores=pagina,
            )

            return

        indice = int(
            query.data.split(
                ":",
                1,
            )[1]
        )

        await mostrar_dia_mercado_completo(
            query,
            context,
            indice,
        )

    except Exception as exc:

        logger.exception(
            "Error al cambiar el día del mercado: %s",
            exc,
        )

        try:
            await query.answer(
                "No se pudo cargar el mercado.",
                show_alert=True,
            )
        except Exception:
            pass


async def mercado_callback(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        accion = query.data.split(
            ":",
            1,
        )[1]

        liga_id = (
            context.user_data.get(
                "liga"
            )
        )

        if not liga_id:

            await query.answer(
                "Primero selecciona una liga.",
                show_alert=True,
            )

            return

        liga_id = int(
            liga_id
        )

        if accion == "completo":

            datos = (
                obtener_mercado_completo_datos(
                    liga_id
                )
            )

            context.user_data[
                "mercado_completo_datos"
            ] = datos

            await mostrar_dia_mercado_completo(
                query,
                context,
                0,
                datos,
            )

        elif accion == "hoy":

            datos = (
                obtener_mercado_hoy_datos(
                    liga_id
                )
            )

            await enviar_mercado_hoy(
                update,
                datos,
            )

        elif accion == "24h":

            guardar_mensaje_anterior(
                query,
                context,
            )

            datos = (
                obtener_mercado_24h_datos(
                    liga_id
                )
            )

            ahora = datos[
                "fecha"
            ]

            movimientos_datos = datos[
                "movimientos"
            ]

            context.user_data[
                "mercado_24h_datos"
            ] = datos

            from biwenger import _nombre_fecha

            titulo = (
                "⏱️ MERCADO — 24H\n"
                "📅 "
                + _nombre_fecha(
                    ahora.timestamp()
                )
            )

            if not movimientos_datos:

                await editar_mensaje(
                    query,
                    (
                        titulo
                        + "\n"
                        + "━━━━━━━━━━━━━━━━━━━━\n\n"
                        + "Sin movimientos."
                    ),
                    teclado_con_fijar(
                        InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    "◀️ Volver a Mercado",
                                    callback_data=(
                                        "menu:mercado"
                                    ),
                                )
                            ]
                        ])
                    ),
                )

            else:

                botones = []

                botones.append([
                    InlineKeyboardButton(
                        "👤 Mostrar Jugadores",
                        callback_data=(
                            "mercado24:mostrar:0"
                        ),
                    )
                ])

                botones.append([
                    InlineKeyboardButton(
                        "◀️ Volver a Mercado",
                        callback_data=(
                            "menu:mercado"
                        ),
                    )
                ])

                await editar_mensaje(
                    query,
                    (
                        titulo
                        + "\n"
                        + "━━━━━━━━━━━━━━━━━━━━\n\n"
                        + "\n\n".join(
                            m.get(
                                "texto",
                                "",
                            )
                            for m in movimientos_datos
                        )
                    ),
                    teclado_con_fijar(
                        InlineKeyboardMarkup(
                            botones
                        )
                    ),
                )
        elif accion == "miembro":

            await mostrar_selector_miembros(
                query,
                liga_id,
            )

        elif accion == "principal":

            await editar_mensaje(
                query,
                texto_menu_liga(
                    context
                ),
                teclado_menu_liga(),
            )

    except Exception:

        logger.exception(
            "ERROR MERCADO CALLBACK"
        )

        try:

            await query.answer(
                "❌ Se produjo un error al consultar el mercado.",
                show_alert=True,
            )

        except Exception:
            pass


async def mercado24_jugadores_callback(
    update,
    context,
):
    query = update.callback_query

    await query.answer()

    try:
        partes = query.data.split(":")

        accion = partes[1]

        pagina = (
            int(partes[2])
            if len(partes) >= 3
            else 0
        )

        datos = context.user_data.get(
            "mercado_24h_datos"
        )

        if not datos:
            liga_id = (
                context.user_data.get(
                    "liga"
                )
            )

            datos = (
                obtener_mercado_24h_datos(
                    int(liga_id)
                )
            )

            context.user_data[
                "mercado_24h_datos"
            ] = datos

        movimientos = datos.get(
            "movimientos",
            [],
        )

        from biwenger import _nombre_fecha

        ahora = datos[
            "fecha"
        ]

        titulo = (
            "⏱️ MERCADO — 24H\n"
            "📅 "
            + _nombre_fecha(
                ahora.timestamp()
            )
        )

        texto = (
            titulo
            + "\n"
            + "━━━━━━━━━━━━━━━━━━━━\n\n"
            + "\n\n".join(
                m.get(
                    "texto",
                    "",
                )
                for m in movimientos
            )
        )

        botones = []

        if accion == "ocultar":

            botones.append([
                InlineKeyboardButton(
                    "👤 Mostrar Jugadores",
                    callback_data=(
                        "mercado24:mostrar:0"
                    ),
                )
            ])

        else:

            botones.append([
                InlineKeyboardButton(
                    "🙈 Ocultar Jugadores",
                    callback_data=(
                        "mercado24:ocultar"
                    ),
                )
            ])

            botones.extend(
                _botones_jugadores_paginados(
                    movimientos,
                    pagina,
                    "mercado24:mostrar",
                )
            )

        botones.append([
            InlineKeyboardButton(
                "◀️ Volver a Mercado",
                callback_data=(
                    "menu:mercado"
                ),
            )
        ])

        await editar_mensaje(
            query,
            texto,
            teclado_con_fijar(
                InlineKeyboardMarkup(
                    botones
                )
            ),
        )

    except Exception:
        logger.exception(
            "ERROR MERCADO 24H JUGADORES"
        )

        await editar_mensaje(
            query,
            "❌ No se pudieron mostrar los jugadores.",
            teclado_submenu_mercado(),
        )

async def mostrar_jornada(
    query,
    context,
    jornada,
    origen="actual",
):
    texto = construir_texto_jornada(
        jornada,
        origen,
    )

    guardar_mensaje_anterior(
        query,
        context,
    )

    context.user_data[
        "jornada_actual"
    ] = jornada

    await editar_mensaje(
        query,
        texto,
        teclado_jornada(
            jornada.get("id"),
            origen,
        ),
    )

async def mercado_hoy_callback(
    update,
    context,
):
    query = update.callback_query

    await query.answer()

    try:

        partes = query.data.split(":")

        if len(partes) < 3:
            raise ValueError(
                "Callback de mercado de hoy inválido"
            )

        tipo = partes[1]

        if tipo not in (
            "sistema",
            "miembros",
            "mios",
        ):
            raise ValueError(
                "Tipo de mercado de hoy inválido"
            )

        posicion = partes[2]

        posiciones_validas = set(
            POSICIONES_MERCADO_HOY_ORDEN
        )

        posiciones_validas.add(
            POSICION_TODAS
        )

        if posicion not in posiciones_validas:
            raise ValueError(
                "Posición de mercado inválida"
            )

        mostrar_jugadores = False
        pagina = 0

        if len(partes) >= 4:

            accion = partes[3]

            if accion == "ocultar":
                mostrar_jugadores = False

            elif accion == "mostrar":

                mostrar_jugadores = True

                if len(partes) >= 5:
                    pagina = int(
                        partes[4]
                    )

            else:
                raise ValueError(
                    "Acción de mercado inválida"
                )

        liga_id = (
            context.user_data.get(
                "liga"
            )
        )

        if not liga_id:

            await query.answer(
                "Primero selecciona una liga.",
                show_alert=True,
            )

            return

        datos = (
            obtener_mercado_hoy_datos(
                int(liga_id)
            )
        )

        guardar_mensaje_anterior(
            query,
            context,
        )

        await mostrar_lista_mercado_hoy(
            query,
            context,
            datos,
            tipo,
            posicion,
            mostrar_jugadores,
            pagina,
        )

    except Exception:

        logger.exception(
            "ERROR MERCADO HOY CALLBACK"
        )

        await editar_mensaje(
            query,
            "❌ No se pudo cargar el mercado de hoy.",
            teclado_mercado_hoy(),
        )

async def mostrar_jornada_actual(
    query,
    context,
):
    try:
        jornada_actual = (
            obtener_jornada_actual()
        )

        if jornada_actual is None:
            await editar_mensaje(
                query,
                (
                    "📅 JORNADA ACTUAL\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "No se pudo encontrar la jornada actual."
                ),
                teclado_submenu_jornadas(),
            )
            return

        await mostrar_jornada(
            query,
            context,
            jornada_actual,
            origen="actual",
        )

    except Exception as exc:
        logger.exception(
            "ERROR JORNADA ACTUAL: %s",
            exc,
        )

        await editar_mensaje(
            query,
            "❌ No se pudo cargar la jornada actual.",
            teclado_submenu_jornadas(),
        )

async def jornadas_callback(
    update,
    context,
):
    query = update.callback_query

    await query.answer()

    try:

        partes = query.data.split(
            ":"
        )

        if len(partes) < 2:
            raise ValueError(
                "Callback de jornadas inválido"
            )

        accion = partes[1]

        if accion == "actual":

            await mostrar_jornada_actual(
                query,
                context,
            )

            return

        if accion == "todas":

            await mostrar_todas_jornadas(
                query,
                context,
                0,
            )

            return

        if (
            accion == "pagina"
            and len(partes) >= 3
        ):

            pagina = int(
                partes[2]
            )

            await mostrar_todas_jornadas(
                query,
                context,
                pagina,
            )

            return

        raise ValueError(
            "Acción de jornadas inválida"
        )

    except Exception as exc:

        logger.exception(
            "ERROR JORNADAS CALLBACK: %s",
            exc,
        )

        await query.answer(
            "❌ No se pudieron cargar las jornadas.",
            show_alert=True,
        )


async def mostrar_ficha_partido(
    query,
    context,
    jornada,
    partido,
):
    home_raw = partido.get("home", "Local")
    away_raw = partido.get("away", "Visitante")

    home_name = _nombre_equipo(home_raw, "Local")
    away_name = _nombre_equipo(away_raw, "Visitante")

    timestamp = _timestamp_partido(partido)

    if timestamp is not None:
        fecha_partido = datetime.fromtimestamp(
            timestamp,
            tz=MADRID_TZ,
        )

        traducciones_dia = {
            "Mon": "Lun",
            "Tue": "Mar",
            "Wed": "Mié",
            "Thu": "Jue",
            "Fri": "Vie",
            "Sat": "Sáb",
            "Sun": "Dom",
        }

        dia = traducciones_dia.get(
            fecha_partido.strftime("%a"),
            fecha_partido.strftime("%a"),
        )

        fecha = (
            f"{dia} "
            f"{fecha_partido.strftime('%d/%m')}"
            f" · "
            f"{fecha_partido.strftime('%H:%M')}"
        )
    else:
        fecha = "Fecha pendiente"

    local_score, away_score, status = (
        _resultado_partido(partido)
    )

    status_text = (
        str(status).strip().lower()
        if status is not None
        else ""
    )

    if (
        local_score is not None
        and away_score is not None
    ):
        resultado = (
            f"🏆 {local_score} — {away_score}"
        )
    else:
        resultado = "🏆 — —"

    if status_text in (
        "finished",
        "final",
        "ended",
        "completed",
        "closed",
        "finished_game",
    ):
        estado_partido = "✅ Finalizado"

    elif status_text in (
        "live",
        "playing",
        "inprogress",
        "in_progress",
        "started",
    ):
        estado_partido = "🔴 En directo"

    elif timestamp is not None:
        ahora = datetime.now(
            tz=MADRID_TZ
        ).timestamp()

        if timestamp <= ahora:
            estado_partido = "🟡 En juego / esperando actualización"
        else:
            estado_partido = "⏳ Pendiente"

    else:
        estado_partido = "⏳ Pendiente"

    lineas = [
        f"⚽ {home_name} — {away_name}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🕐 {fecha}",
        f"{resultado}",
        f"📌 {estado_partido}",
        "",
    ]

    imagenes = []

    for team_key, opponent_raw in (
        ("home", away_raw),
        ("away", home_raw),
    ):
        team = partido.get(team_key)

        if not isinstance(team, dict):
            continue

        try:
            jugadores, confirmed = obtener_alineacion_mostrable(
                partido,
                team_key,
            )

            if not jugadores:
                continue

            opponent = (
                opponent_raw
                if isinstance(opponent_raw, dict)
                else {
                    "name": _nombre_equipo(
                        opponent_raw,
                        "",
                    )
                }
            )

            imagen = generar_imagen_alineacion(
                team,
                opponent=opponent,
                confirmed=confirmed,
                game=partido,
                team_key=team_key,
            )

            imagenes.append(
                (
                    team_key,
                    imagen,
                    confirmed,
                )
            )

        except LineupImageError as exc:
            logger.info(
                "Sin alineación %s para partido %s: %s",
                team_key,
                partido.get("id"),
                exc,
            )

        except Exception:
            logger.exception(
                "ERROR GENERANDO IMAGEN ALINEACIÓN %s",
                team_key,
            )

    if imagenes:
        estado = (
            "11 inicial"
            if any(item[2] for item in imagenes)
            else "11 posible"
        )
    else:
        estado = "No disponible"

    lineas.extend([
        f"📋 Alineaciones: {estado}",
        "",
        "Selecciona una opción:",
    ])

    botones = [
        [
            InlineKeyboardButton(
                "◀️ Volver a Partidos",
                callback_data=(
                    f"jornada:partidos:"
                    f"{jornada.get('id')}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Volver a Jornada",
                callback_data=(
                    f"jornada:"
                    f"{jornada.get('id')}"
                ),
            )
        ],
    ]

    await editar_mensaje(
        query,
        "\n".join(lineas),
        teclado_con_fijar(
            InlineKeyboardMarkup(botones)
        ),
    )

    for team_key, imagen, confirmed in imagenes:
        try:
            caption = (
                "11 inicial"
                if confirmed
                else "11 posible"
            )

            await query.message.reply_photo(
                photo=InputFile(imagen),
                caption=caption,
            )

        except Exception:
            logger.exception(
                "ERROR ENVIANDO IMAGEN ALINEACIÓN %s",
                team_key,
            )

async def mostrar_partidos_jornada(
    query,
    context,
    jornada,
):
    games = jornada.get(
        "games",
        [],
    )

    numero_jornada = jornada.get(
        "short",
        "J?",
    )

    texto = (
        f"⚽ PARTIDOS — {numero_jornada}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Selecciona un partido:"
    )

    botones = []

    for partido in games:

        if not isinstance(
            partido,
            dict,
        ):
            continue

        partido_id = (
            partido.get("id")
            or partido.get("gameId")
        )

        if partido_id is None:
            continue

        home = _nombre_equipo(
            partido.get("home"),
            "Local",
        )

        away = _nombre_equipo(
            partido.get("away"),
            "Visitante",
        )

        local_score, away_score, status = (
            _resultado_partido(partido)
        )

        # -------------------------------------------------
        # Estado del partido
        # -------------------------------------------------

        estado = ""

        status_text = (
            str(status).strip().lower()
            if status is not None
            else ""
        )

        finalizado = status_text in (
            "finished",
            "final",
            "ended",
            "completed",
            "closed",
            "finished_game",
        )

        if (
            local_score is not None
            and away_score is not None
        ):
            marcador = (
                f"{local_score}-{away_score}"
            )

            prefijo = "✅"

            if finalizado:
                estado = (
                    f" {prefijo} {marcador}"
                )
            else:
                estado = (
                    f" ⚽ {marcador}"
                )

        elif finalizado:
            estado = " ✅"

        else:
            estado = " ⏳"

        botones.append([
            InlineKeyboardButton(
                (
                    f"{home} — {away}"
                    f"{estado}"
                ),
                callback_data=(
                    f"jornada:partido:"
                    f"{jornada.get('id')}:"
                    f"{partido_id}"
                ),
            )
        ])

    botones.append([
        InlineKeyboardButton(
            "◀️ Volver a Jornada",
            callback_data=(
                f"jornada:"
                f"{jornada.get('id')}"
            ),
        )
    ])

    await editar_mensaje(
        query,
        texto,
        teclado_con_fijar(
            InlineKeyboardMarkup(
                botones
            )
        ),
    )


async def jornada_callback(
    update,
    context,
):
    query = update.callback_query

    await query.answer()

    try:

        partes = query.data.split(":")

        if not partes or partes[0] != "jornada":
            raise ValueError(
                "Callback de jornada inválido"
            )

        # -------------------------------------------------
        # ACCIONES DE LA JORNADA
        # -------------------------------------------------

        if len(partes) >= 2:

            accion = partes[1]

            # ---------------------------------------------
            # PARTIDOS — SUBMENÚ DE PARTIDOS
            # ---------------------------------------------

            if accion == "partidos":

                if len(partes) < 3:
                    raise ValueError(
                        "Falta el ID de la jornada"
                    )

                jornada_id = int(
                    partes[2]
                )

                jornada = obtener_jornada(
                    jornada_id
                )

                if jornada is None:
                    await query.answer(
                        "❌ No se encontró la jornada.",
                        show_alert=True,
                    )
                    return

                context.user_data[
                    "jornada_actual"
                ] = jornada

                await mostrar_partidos_jornada(
                    query,
                    context,
                    jornada,
                )

                return

            # ---------------------------------------------
            # PARTIDO — FICHA DE UN PARTIDO
            # ---------------------------------------------

            if accion == "partido":

                if len(partes) < 4:
                    raise ValueError(
                        "Faltan datos del partido"
                    )

                jornada_id = int(
                    partes[2]
                )

                partido_id = int(
                    partes[3]
                )

                jornada = obtener_jornada(
                    jornada_id
                )

                if jornada is None:
                    await query.answer(
                        "❌ No se encontró la jornada.",
                        show_alert=True,
                    )
                    return

                partido = None

                for game in jornada.get(
                    "games",
                    [],
                ):

                    if not isinstance(
                        game,
                        dict,
                    ):
                        continue

                    game_id = (
                        game.get("id")
                        or game.get("gameId")
                    )

                    if (
                        game_id is not None
                        and int(game_id)
                        == partido_id
                    ):
                        partido = game
                        break

                if partido is None:
                    await query.answer(
                        "❌ No se encontró el partido.",
                        show_alert=True,
                    )
                    return

                context.user_data[
                    "jornada_actual"
                ] = jornada

                context.user_data[
                    "partido_actual"
                ] = partido

                await mostrar_ficha_partido(
                    query,
                    context,
                    jornada,
                    partido,
                )

                return


            # ---------------------------------------------
            # ONCES
            # ---------------------------------------------

            if accion == "onces":

                await query.answer(
                    "🚧 Onces elegidos: próximamente.",
                    show_alert=True,
                )

                return

            # ---------------------------------------------
            # MI JORNADA
            # ---------------------------------------------

            if accion == "mi_jornada":

                await query.answer(
                    "🚧 Mi jornada: próximamente.",
                    show_alert=True,
                )

                return

        # -------------------------------------------------
        # JORNADA NORMAL
        # -------------------------------------------------

        if len(partes) not in (2, 3):
            raise ValueError(
                "Callback de jornada inválido"
            )

        jornada_id = int(
            partes[1]
        )

        origen = (
            partes[2]
            if len(partes) == 3
            else "actual"
        )

        if origen not in (
            "actual",
            "todas",
        ):
            origen = "actual"

        jornada = obtener_jornada(
            jornada_id
        )

        if jornada is None:

            await query.answer(
                "❌ No se encontró la jornada.",
                show_alert=True,
            )

            return

        context.user_data[
            "jornada_actual"
        ] = jornada

        await mostrar_jornada(
            query,
            context,
            jornada,
            origen=origen,
        )

    except Exception as exc:

        logger.exception(
            "ERROR JORNADA CALLBACK: %s",
            exc,
        )

        await query.answer(
            "❌ No se pudo cargar la jornada.",
            show_alert=True,
        )

async def error_handler(
    update,
    context,
):
    logger.error(
        "ERROR GLOBAL: %s",
        context.error,
        exc_info=context.error,
    )

def main():

    app = (
        Application
        .builder()
        .token(
            TELEGRAM_TOKEN
        )
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "liga",
            liga,
        )
    )

    app.add_handler(
        CommandHandler(
            "informe",
            informe,
        )
    )

    app.add_handler(
        CommandHandler(
            "mercado",
            mercado,
        )
    )

    app.add_handler(
        CommandHandler(
            "movimientos",
            movimientos,
        )
    )

    app.add_handler(
        CommandHandler(
            "mercado24",
            mercado24,
        )
    )

    app.add_handler(
        CommandHandler(
            "mercadohoy",
            mercadohoy,
        )
    )

    app.add_handler(
        CommandHandler(
            "mercadomiembro",
            mercadomiembro,
        )
    )

    app.add_handler(
        CommandHandler(
            "ayuda",
            ayuda,
        )
    )

    # -----------------------------
    # CALLBACKS
    # -----------------------------

    app.add_handler(
        CallbackQueryHandler(
            noop_callback,
            pattern=r"^noop$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            elegir_liga,
            pattern=r"^liga:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            menu_callback,
            pattern=r"^menu:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            mercado_callback,
            pattern=r"^mercado:",
        )
    )


    app.add_handler(
        CallbackQueryHandler(
            mercado24_jugadores_callback,
            pattern=r"^mercado24:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            elegir_miembro,
            pattern=r"^miembro:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            cambiar_dia_miembro,
            pattern=r"^miembrodia:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            volver_miembros,
            pattern=r"^miembros:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            mercado_hoy_callback,
            pattern=r"^mercadohoy:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            cambiar_dia_mercado_completo,
            pattern=r"^completodia:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            jornadas_callback,
            pattern=r"^jornadas:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            jornada_callback,
            pattern=r"^jornada:",
       )
    )

    app.add_handler(
        CallbackQueryHandler(
            ficha_jugador,
            pattern=r"^jugador:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            fijar_mensaje,
            pattern=r"^fijar_mensaje$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            fijar_jugador,
            pattern=r"^fijar:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            volver_desde_jugador,
            pattern=r"^jugador_anterior$",
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        "Bot iniciado..."
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()