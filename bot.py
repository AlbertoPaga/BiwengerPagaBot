import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
    obtener_miembros_liga,
    obtener_mercado_miembro_datos,
    obtener_ficha_jugador,
)

# ============================================================
# LOGS INTERNOS
# ============================================================

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(__name__)

MAX_TELEGRAM = 4000


# ============================================================
# UTILIDADES
# ============================================================

def formatear_dinero(valor):
    try:
        return f"{int(valor):,}€"

    except Exception:
        return "0€"


# ============================================================
# EDITAR MENSAJE CON SEGURIDAD
# ============================================================

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


# ============================================================
# ENVIAR MENSAJES LARGOS
# ============================================================

async def enviar_largo(
    update,
    texto,
):

    if not texto:
        texto = "Sin datos"

    partes = [
        texto[i:i + MAX_TELEGRAM]
        for i in range(
            0,
            len(texto),
            MAX_TELEGRAM,
        )
    ]

    for parte in partes:

        if update.message is not None:

            await update.message.reply_text(
                parte
            )

        elif update.callback_query is not None:

            await update.callback_query.message.reply_text(
                parte
            )


# ============================================================
# BOTÓN DE JUGADOR
# ============================================================

def boton_jugador(
    player_id,
    player_name,
):

    if player_id is None:
        return None

    try:

        player_id = int(player_id)

    except (
        TypeError,
        ValueError,
    ):

        return None

    return InlineKeyboardButton(
        f"⚽ {player_name}",
        callback_data=f"jugador:{player_id}",
    )


# ============================================================
# SELECTOR DE LIGA
# ============================================================

async def mostrar_selector_liga(
    update,
):

    ligas = obtener_ligas()

    botones = []

    for liga in ligas:

        if not isinstance(
            liga,
            dict,
        ):
            continue

        liga_id = liga.get("id")

        nombre = liga.get(
            "name",
            f"Liga {liga_id}",
        )

        if liga_id is None:
            continue

        botones.append([
            InlineKeyboardButton(
                str(nombre),
                callback_data=f"liga:{liga_id}",
            )
        ])

    if not botones:

        await update.message.reply_text(
            "No se encontraron ligas."
        )

        return

    await update.message.reply_text(
        "🏆 Selecciona una liga:",
        reply_markup=InlineKeyboardMarkup(
            botones
        ),
    )


# ============================================================
# MENÚ DE LIGA
# ============================================================

async def mostrar_menu_liga(
    update,
    context,
):

    nombre = context.user_data.get(
        "liga_nombre",
        "Liga seleccionada",
    )

    await update.message.reply_text(
        f"🏆 {nombre}\n\n"
        "Comandos disponibles:\n\n"
        "/informe\n"
        "/mercado\n"
        "/mercado24\n"
        "/mercadomiembro\n"
        "/liga\n"
        "/ayuda"
    )


# ============================================================
# START
# ============================================================

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

    else:

        await update.message.reply_text(
            "🤖 ConsultasBiwenger\n\n"
            "Primero selecciona una liga."
        )

        await mostrar_selector_liga(
            update
        )


# ============================================================
# CAMBIAR DE LIGA
# ============================================================

async def liga(
    update,
    context,
):

    try:

        await mostrar_selector_liga(
            update
        )

    except Exception as e:

        logger.exception(
            "ERROR LIGA"
        )

        await update.message.reply_text(
            f"Error obteniendo ligas:\n{e}"
        )


# ============================================================
# ELEGIR LIGA
# ============================================================

async def elegir_liga(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        if not query.data.startswith("liga:"):

            raise ValueError(
                "Callback de liga inválido"
            )

        liga_id = int(
            query.data.split(
                ":",
                1
            )[1]
        )

        ligas = obtener_ligas()

        liga_encontrada = next(
            (
                liga
                for liga in ligas
                if (
                    isinstance(liga, dict)
                    and
                    str(liga.get("id"))
                    == str(liga_id)
                )
            ),
            None,
        )

        if liga_encontrada is None:

            raise ValueError(
                "La liga seleccionada ya no está disponible."
            )

        liga_nombre = liga_encontrada.get(
            "name",
            f"Liga {liga_id}",
        )

    except Exception:

        logger.exception(
            "ERROR ELEGIR LIGA"
        )

        await editar_mensaje(
            query,
            "❌ No se pudo seleccionar la liga.",
        )

        return

    context.user_data["liga"] = liga_id

    context.user_data["liga_nombre"] = liga_nombre

    await editar_mensaje(
        query,
        (
            f"🏆 {liga_nombre}\n\n"
            "Selecciona una opción:"
        ),
        InlineKeyboardMarkup([
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
                    "⏱️ Mercado de hoy",
                    callback_data="menu:mercado24",
                )
            ],
            [
                InlineKeyboardButton(
                    "🧑‍💼 Mercado por miembro",
                    callback_data="menu:mercadomiembro",
                )
            ],
        ]),
    )


# ============================================================
# COMPROBAR LIGA ACTIVA
# ============================================================

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

        return None

    return int(liga_id)


# ============================================================
# INFORME
# ============================================================

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

        mensaje_carga = await update.message.reply_text(
            "📊 Calculando informe..."
        )

        report = obtener_informe(
            liga_id
        )

        texto = (
            "📊 INFORME DE MANAGERS\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if not report:

            texto += (
                "No se han encontrado "
                "miembros en esta liga."
            )

            await mensaje_carga.edit_text(
                texto
            )

            return

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
                f"⚽ Jugadores: "
                f"{numero_jugadores}\n"
                f"🟢 Compras: "
                f"{formatear_dinero(compras)}\n"
                f"🔴 Ventas: "
                f"{formatear_dinero(ventas)}\n"
                f"💰 Saldo: "
                f"{formatear_dinero(saldo)}\n"
                f"💵 Puja máxima: "
                f"{formatear_dinero(puja_maxima)}\n\n"
            )

        if len(texto) <= MAX_TELEGRAM:

            await mensaje_carga.edit_text(
                texto
            )

        else:

            await mensaje_carga.delete()

            await enviar_largo(
                update,
                texto,
            )

    except Exception as e:

        logger.exception(
            "ERROR INFORME"
        )

        await update.message.reply_text(
            f"Error calculando informe:\n{e}"
        )


# ============================================================
# CONSTRUIR TECLADO DE MOVIMIENTO
# ============================================================

def construir_botones_movimientos(
    movimientos,
):

    botones = []

    for movimiento in movimientos:

        player_id = movimiento.get(
            "player_id"
        )

        player_name = movimiento.get(
            "player_name",
            "Jugador",
        )

        boton = boton_jugador(
            player_id,
            player_name,
        )

        if boton is not None:

            botones.append([
                boton
            ])

    return botones


# ============================================================
# ENVIAR MOVIMIENTOS
# ============================================================

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

            return await update.message.reply_text(
                texto
            )

        if update.callback_query is not None:

            return await update.callback_query.message.reply_text(
                texto
            )

        return None

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

        player_id = movimiento.get(
            "player_id"
        )

        player_name = movimiento.get(
            "player_name",
            "Jugador",
        )

        boton = boton_jugador(
            player_id,
            player_name,
        )

        texto_candidato = (
            texto_actual
            + texto_movimiento
            + "\n\n"
        )

        if len(texto_candidato) > MAX_TELEGRAM:

            markup = (
                InlineKeyboardMarkup(
                    botones_actuales
                )
                if botones_actuales
                else None
            )

            if update.message is not None:

                mensaje = await update.message.reply_text(
                    texto_actual.rstrip(),
                    reply_markup=markup,
                )

            else:

                mensaje = await update.callback_query.message.reply_text(
                    texto_actual.rstrip(),
                    reply_markup=markup,
                )

            mensajes.append(mensaje)

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
            InlineKeyboardMarkup(
                botones_actuales
            )
            if botones_actuales
            else None
        )

        if update.message is not None:

            mensaje = await update.message.reply_text(
                texto_actual.rstrip(),
                reply_markup=markup,
            )

        else:

            mensaje = await update.callback_query.message.reply_text(
                texto_actual.rstrip(),
                reply_markup=markup,
            )

        mensajes.append(mensaje)

    return mensajes


# ============================================================
# MERCADO COMPLETO
# ============================================================

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

        mensaje_carga = await update.message.reply_text(
            "🔄 Cargando mercado completo..."
        )

        datos = obtener_mercado_completo_datos(
            liga_id
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

            await mensaje_carga.edit_text(
                "🔄 MERCADO COMPLETO\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Sin movimientos."
            )

            return

        from biwenger import _nombre_fecha

        await mensaje_carga.delete()

        for clave in orden:

            if clave == "desconocida":

                titulo = "📅 FECHA DESCONOCIDA"

            else:

                titulo = (
                    "📅 "
                    + _nombre_fecha(
                        timestamps.get(
                            clave
                        )
                    )
                )

            await enviar_movimientos(
                update,
                titulo,
                grupos.get(
                    clave,
                    [],
                ),
            )

    except Exception as e:

        logger.exception(
            "ERROR MERCADO"
        )

        await update.message.reply_text(
            f"Error obteniendo mercado:\n{e}"
        )


# ============================================================
# ALIAS MOVIMIENTOS
# ============================================================

async def movimientos(
    update,
    context,
):

    await mercado(
        update,
        context,
    )


# ============================================================
# MERCADO DEL DÍA
# ============================================================

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

        mensaje_carga = await update.message.reply_text(
            "⏱️ Cargando mercado de hoy..."
        )

        datos = obtener_mercado_24h_datos(
            liga_id
        )

        ahora = datos["fecha"]

        movimientos_datos = datos["movimientos"]

        from biwenger import _nombre_fecha

        titulo = (
            "⏱️ MERCADO — HOY\n"
            "📅 "
            + _nombre_fecha(
                ahora.timestamp()
            )
        )

        if not movimientos_datos:

            await mensaje_carga.edit_text(
                titulo
                + "\n"
                + "━━━━━━━━━━━━━━━━━━━━\n\n"
                + "Sin movimientos."
            )

            return

        texto = (
            titulo
            + "\n"
            + "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        botones = []

        for movimiento in movimientos_datos:

            texto += (
                movimiento.get(
                    "texto",
                    "",
                )
                + "\n\n"
            )

            boton = boton_jugador(
                movimiento.get(
                    "player_id"
                ),
                movimiento.get(
                    "player_name",
                    "Jugador",
                ),
            )

            if boton is not None:

                botones.append([
                    boton
                ])

        markup = (
            InlineKeyboardMarkup(
                botones
            )
            if botones
            else None
        )

        if len(texto) <= MAX_TELEGRAM:

            await mensaje_carga.edit_text(
                texto.rstrip(),
                reply_markup=markup,
            )

        else:

            await mensaje_carga.delete()

            await enviar_movimientos(
                update,
                titulo,
                movimientos_datos,
            )

    except Exception as e:

        logger.exception(
            "ERROR MERCADO 24H"
        )

        await update.message.reply_text(
            f"Error obteniendo mercado:\n{e}"
        )


# ============================================================
# FORMATEAR FECHA PARA BOTÓN
# ============================================================

def formatear_fecha_boton(
    timestamp,
):
    """
    Convierte un timestamp de mercado
    a formato DD/MM/YY.

    Ejemplo:
    8 agosto 2026 -> 08/08/26
    """

    try:

        from datetime import datetime

        fecha = datetime.fromtimestamp(
            float(timestamp)
        )

        return fecha.strftime(
            "%d/%m/%y"
        )

    except Exception:

        return "Fecha"


# ============================================================
# CONSTRUIR MENSAJE DE UN DÍA DE UN MIEMBRO
# ============================================================

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

    if indice < 0:
        indice = 0

    if indice >= len(orden):
        indice = len(orden) - 1

    clave = orden[indice]

    from biwenger import _nombre_fecha

    if clave == "desconocida":

        titulo_fecha = "📅 FECHA DESCONOCIDA"

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


# ============================================================
# BOTONES DE NAVEGACIÓN DE DÍAS
#
# ORDEN:
#
# 1. JUGADORES
# 2. FECHAS
# 3. CAMBIAR MIEMBRO
#
# ============================================================

def construir_botones_dias(
    liga_id,
    miembro_id,
    indice,
    total_dias,
    movimientos,
    timestamps,
    orden,
):

    botones = []

    # --------------------------------------------------------
    # 1. BOTONES DE JUGADORES
    # --------------------------------------------------------

    for movimiento in movimientos:

        boton = boton_jugador(
            movimiento.get(
                "player_id"
            ),
            movimiento.get(
                "player_name",
                "Jugador",
            ),
        )

        if boton is not None:

            botones.append([
                boton
            ])

    # --------------------------------------------------------
    # 2. BOTONES DE FECHAS
    #
    # Mostramos todas las fechas disponibles.
    # La fecha seleccionada se muestra pero no es clicable.
    #
    # Ejemplo:
    #
    # 08/08/26
    # 07/08/26
    # 06/08/26
    # 05/08/26
    #
    # --------------------------------------------------------

    botones_fechas = []

    for posicion, clave in enumerate(orden):

        if clave == "desconocida":

            texto_fecha = "❓ Desconocida"

        else:

            timestamp = timestamps.get(
                clave
            )

            texto_fecha = formatear_fecha_boton(
                timestamp
            )

        # Día actual seleccionado:
        # botón visualmente marcado y sin callback.
        if posicion == indice:

            botones_fechas.append(
                InlineKeyboardButton(
                    f"📅 {texto_fecha}",
                    callback_data="noop",
                )
            )

        else:

            botones_fechas.append(
                InlineKeyboardButton(
                    texto_fecha,
                    callback_data=(
                        f"miembrodia:"
                        f"{liga_id}:"
                        f"{miembro_id}:"
                        f"{posicion}"
                    ),
                )
            )

    # --------------------------------------------------------
    # Las fechas van en filas de dos botones.
    # --------------------------------------------------------

    for i in range(
        0,
        len(botones_fechas),
        2,
    ):

        fila = botones_fechas[i:i + 2]

        botones.append(
            fila
        )

    # --------------------------------------------------------
    # 3. CAMBIAR MIEMBRO
    # --------------------------------------------------------

    botones.append([
        InlineKeyboardButton(
            "👥 Cambiar miembro",
            callback_data=(
                f"miembros:{liga_id}"
            ),
        )
    ])

    return InlineKeyboardMarkup(
        botones
    )


# ============================================================
# MOSTRAR DÍA DE MERCADO DE MIEMBRO
# ============================================================

async def mostrar_dia_miembro(
    query,
    liga_id,
    miembro_id,
    indice,
    datos=None,
):

    try:

        if datos is None:

            datos = obtener_mercado_miembro_datos(
                liga_id,
                miembro_id,
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

            await editar_mensaje(
                query,
                (
                    f"🧑‍💼 MERCADO — "
                    f"{nombre_miembro}\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Sin movimientos."
                ),
                InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "👥 Cambiar miembro",
                            callback_data=(
                                f"miembros:{liga_id}"
                            ),
                        )
                    ]
                ]),
            )

            return

        if indice < 0:
            indice = 0

        if indice >= len(orden):
            indice = len(orden) - 1

        clave = orden[indice]

        movimientos = grupos.get(
            clave,
            [],
        )

        texto = construir_mensaje_dia_miembro(
            nombre_miembro,
            grupos,
            orden,
            timestamps,
            indice,
        )

        if len(texto) > MAX_TELEGRAM:

            texto = texto[
                :MAX_TELEGRAM - 50
            ]

            texto += "\n\n…"

        teclado = construir_botones_dias(
            liga_id,
            miembro_id,
            indice,
            len(orden),
            movimientos,
            timestamps,
            orden,
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
            "❌ No se pudieron obtener "
            "los movimientos del miembro.",
        )


# ============================================================
# MERCADO POR MIEMBRO
# ============================================================

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
                "❌ No se encontraron miembros "
                "en esta liga."
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
                "❌ No se pudieron cargar "
                "los miembros."
            )

            return

        await update.message.reply_text(
            "🧑‍💼 Selecciona un miembro:",
            reply_markup=InlineKeyboardMarkup(
                botones
            ),
        )

    except Exception as e:

        logger.exception(
            "ERROR MERCADO POR MIEMBRO"
        )

        await update.message.reply_text(
            f"Error obteniendo miembros:\n{e}"
        )


# ============================================================
# MOSTRAR SELECTOR DE MIEMBROS
# ============================================================

async def mostrar_selector_miembros(
    query,
    liga_id,
):

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

    await editar_mensaje(
        query,
        "🧑‍💼 Selecciona un miembro:",
        InlineKeyboardMarkup(
            botones
        ),
    )


# ============================================================
# ELEGIR MIEMBRO
# ============================================================

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

        liga_actual = context.user_data.get(
            "liga"
        )

        if (
            liga_actual is None
            or int(liga_actual) != liga_id
        ):

            raise ValueError(
                "La liga seleccionada ya no coincide."
            )

        await editar_mensaje(
            query,
            "🔄 Cargando movimientos..."
        )

        datos = obtener_mercado_miembro_datos(
            liga_id,
            miembro_id,
        )

        await mostrar_dia_miembro(
            query,
            liga_id,
            miembro_id,
            0,
            datos,
        )

    except Exception:

        logger.exception(
            "ERROR ELEGIR MIEMBRO"
        )

        try:

            await editar_mensaje(
                query,
                "❌ No se pudieron obtener "
                "los movimientos del miembro.",
            )

        except Exception:

            await query.message.reply_text(
                "❌ No se pudieron obtener "
                "los movimientos del miembro."
            )


# ============================================================
# CAMBIAR DÍA DE MERCADO DE MIEMBRO
# ============================================================

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

        if len(partes) != 4:

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

        liga_actual = context.user_data.get(
            "liga"
        )

        if (
            liga_actual is None
            or int(liga_actual) != liga_id
        ):

            raise ValueError(
                "La liga seleccionada ya no coincide."
            )

        await mostrar_dia_miembro(
            query,
            liga_id,
            miembro_id,
            indice,
        )

    except Exception:

        logger.exception(
            "ERROR CAMBIAR DÍA MIEMBRO"
        )

        try:

            await editar_mensaje(
                query,
                "❌ No se pudo cambiar de día.",
            )

        except Exception:

            await query.message.reply_text(
                "❌ No se pudo cambiar de día."
            )


# ============================================================
# BOTÓN NOOP
# ============================================================

async def noop_callback(
    update,
    context,
):

    query = update.callback_query

    await query.answer()


# ============================================================
# VOLVER AL SELECTOR DE MIEMBROS
# ============================================================

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

        liga_actual = context.user_data.get(
            "liga"
        )

        if (
            liga_actual is None
            or int(liga_actual) != liga_id
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
            "❌ No se pudo volver a "
            "la selección de miembros.",
        )


# ============================================================
# FICHA DEL JUGADOR
# ============================================================

async def ficha_jugador(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

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
                1
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

        nombre = jugador.get(
            "nombre",
            "Desconocido",
        )

        equipo = jugador.get(
            "equipo",
            "?",
        )

        precio = jugador.get(
            "precio",
            0,
        )

        puntos = jugador.get(
            "puntos",
            0,
        )

        texto = (
            f"⚽ {nombre}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏟️ Equipo: {equipo}\n"
            f"💰 Precio: "
            f"{formatear_dinero(precio)}\n"
            f"⭐ Puntos: {puntos}\n"
        )

        await query.answer(
            texto,
            show_alert=True,
        )

    except Exception:

        logger.exception(
            "ERROR FICHA JUGADOR"
        )

        try:

            await query.answer(
                "❌ No se pudo obtener "
                "la ficha del jugador.",
                show_alert=True,
            )

        except Exception:

            pass


# ============================================================
# AYUDA
# ============================================================

async def ayuda(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )

    if liga_id:

        texto = (
            "📚 Comandos disponibles:\n\n"
            "/informe\n"
            "Informe de managers, jugadores, "
            "compras, ventas, saldo y puja máxima.\n\n"
            "/mercado\n"
            "Mercado completo agrupado por fechas.\n\n"
            "/mercado24\n"
            "Movimientos del día actual, desde "
            "las 00:00 hasta el momento de la consulta.\n\n"
            "/mercadomiembro\n"
            "Movimientos de mercado de un miembro "
            "concreto, agrupados por días y navegables "
            "con botones.\n\n"
            "/liga\n"
            "Cambiar de liga.\n\n"
            "/ayuda\n"
            "Mostrar ayuda."
        )

    else:

        texto = (
            "📚 Comandos:\n\n"
            "/start\n"
            "Iniciar bot y seleccionar liga.\n\n"
            "/liga\n"
            "Seleccionar liga."
        )

    await update.message.reply_text(
        texto
    )


# ============================================================
# MENÚ POR BOTONES
# ============================================================

async def menu_callback(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        accion = query.data.split(
            ":",
            1
        )[1]

        if accion == "informe":

            await query.message.reply_text(
                "Usa /informe para consultar el informe."
            )

        elif accion == "mercado":

            await query.message.reply_text(
                "Usa /mercado para consultar el mercado."
            )

        elif accion == "mercado24":

            await query.message.reply_text(
                "Usa /mercado24 para consultar el mercado de hoy."
            )

        elif accion == "mercadomiembro":

            # IMPORTANTE:
            # Ya NO dice simplemente que uses el comando.
            # El botón abre directamente el selector
            # de miembros.

            liga_id = context.user_data.get(
                "liga"
            )

            if not liga_id:

                await query.message.reply_text(
                    "❌ Primero selecciona una liga."
                )

                return

            await mostrar_selector_miembros(
                query,
                int(liga_id),
            )

    except Exception:

        logger.exception(
            "ERROR MENU CALLBACK"
        )


# ============================================================
# MANEJADOR GLOBAL DE ERRORES
# ============================================================

async def error_handler(
    update,
    context,
):

    logger.error(
        "ERROR GLOBAL: %s",
        context.error,
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    app = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # COMANDOS PRINCIPALES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # BOTONES INLINE
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            elegir_liga,
            pattern=r"^liga:",
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
            ficha_jugador,
            pattern=r"^jugador:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            menu_callback,
            pattern=r"^menu:",
        )
    )

    # Botón de fecha actualmente seleccionada
    app.add_handler(
        CallbackQueryHandler(
            noop_callback,
            pattern=r"^noop$",
        )
    )

    # --------------------------------------------------------
    # MANEJADOR GLOBAL DE ERRORES
    # --------------------------------------------------------

    app.add_error_handler(
        error_handler
    )

    print(
        "Bot iniciado..."
    )

    app.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()