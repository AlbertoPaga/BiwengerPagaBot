import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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
)


# ============================================================
# LOGS
# ============================================================

logging.basicConfig(level=logging.INFO)
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


def formatear_fecha_boton(timestamp):
    """Convierte el timestamp de Biwenger a dd/MM/yy."""
    if timestamp is None:
        return "??/??/??"

    try:
        from datetime import datetime

        fecha = datetime.fromtimestamp(float(timestamp))
        return fecha.strftime("%d/%m/%y")
    except Exception:
        return "??/??/??"


# ============================================================
# EDITAR MENSAJE CON SEGURIDAD
# ============================================================

async def editar_mensaje(query, texto, reply_markup=None):
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
# BOTÓN DE JUGADOR
# ============================================================

def boton_jugador(player_id, player_name):
    if player_id is None:
        return None

    try:
        player_id = int(player_id)
    except (TypeError, ValueError):
        return None

    return InlineKeyboardButton(
        f"⚽ {player_name}",
        callback_data=f"jugador:{player_id}",
    )


def boton_jugador_mercado(venta):
    """Botón del jugador del sistema que está actualmente en venta."""
    player_id = venta.get("player_id")
    player_name = venta.get("player_name", "Jugador")
    price = formatear_dinero(venta.get("price", 0))

    if player_id is None:
        return None

    try:
        player_id = int(player_id)
    except (TypeError, ValueError):
        return None

    return InlineKeyboardButton(
        f"⚽ {player_name} — {price}",
        callback_data=f"jugador:{player_id}",
    )


# ============================================================
# MENÚ DE LIGA
# ============================================================

def teclado_menu_liga():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Informe", callback_data="menu:informe")],
        [InlineKeyboardButton("🔄 Mercado", callback_data="menu:mercado")],
        [InlineKeyboardButton("🏆 Cambiar liga", callback_data="menu:liga")],
    ])


def texto_menu_liga(context):
    nombre = context.user_data.get("liga_nombre", "Liga seleccionada")

    return (
        f"🏆 {nombre}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Selecciona una opción:"
    )


async def mostrar_menu_liga(update, context):
    texto = texto_menu_liga(context)

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


# ============================================================
# SUBMENÚ DE MERCADO
# ============================================================

def teclado_submenu_mercado():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Mercado completo", callback_data="mercado:completo")],
        [InlineKeyboardButton("📅 Mercado de hoy", callback_data="mercado:hoy")],
        [InlineKeyboardButton("⏱️ Mercado 24h", callback_data="mercado:24h")],
        [InlineKeyboardButton("🧑‍💼 Mercado por miembro", callback_data="mercado:miembro")],
        [InlineKeyboardButton("◀️ Volver", callback_data="menu:principal")],
    ])


def teclado_mercado_hoy():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🤖 Jugadores en Venta Sistema",
                callback_data="mercadohoy:sistema",
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Jugadores en Venta Miembros",
                callback_data="mercadohoy:miembros",
            )
        ],
        [
            InlineKeyboardButton(
                "◀️ Volver a Mercado",
                callback_data="menu:mercado",
            )
        ],
    ])


def teclado_lista_mercado_hoy():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "◀️ Volver a Mercado de Hoy",
                callback_data="mercado:hoy",
            )
        ],
    ])


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


async def mostrar_submenu_mercado(update, context, editar=True):
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


# ============================================================
# START
# ============================================================

async def start(update, context):
    liga_id = context.user_data.get("liga")

    if liga_id:
        await mostrar_menu_liga(update, context)
        return

    mensaje = await update.message.reply_text(
        "🤖 ConsultasBiwenger\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Primero selecciona una liga."
    )

    await mostrar_selector_liga(update, mensaje=mensaje)


# ============================================================
# SELECTOR DE LIGA
# ============================================================

async def mostrar_selector_liga(update, mensaje=None):
    ligas = obtener_ligas()
    botones = []

    for liga in ligas:
        if not isinstance(liga, dict):
            continue

        liga_id = liga.get("id")
        nombre = liga.get("name", f"Liga {liga_id}")

        if liga_id is None:
            continue

        botones.append([
            InlineKeyboardButton(
                str(nombre),
                callback_data=f"liga:{liga_id}",
            )
        ])

    if not botones:
        if mensaje is not None:
            await mensaje.edit_text("❌ No se encontraron ligas.")
        elif update.message is not None:
            await update.message.reply_text(
                "❌ No se encontraron ligas."
            )
        return

    markup = InlineKeyboardMarkup(botones)

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


# ============================================================
# COMANDO /LIGA
# ============================================================

async def liga(update, context):
    try:
        await mostrar_selector_liga(update)
    except Exception as exc:
        logger.exception("ERROR LIGA")
        await update.message.reply_text(
            f"Error obteniendo ligas:\n{exc}"
        )


# ============================================================
# ELEGIR LIGA
# ============================================================

async def elegir_liga(update, context):
    query = update.callback_query
    await query.answer()

    try:
        if not query.data.startswith("liga:"):
            raise ValueError("Callback de liga inválido")

        liga_id = int(
            query.data.split(":", 1)[1]
        )

        ligas = obtener_ligas()

        liga_encontrada = next(
            (
                liga
                for liga in ligas
                if (
                    isinstance(liga, dict)
                    and str(liga.get("id"))
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

        context.user_data["liga"] = liga_id
        context.user_data["liga_nombre"] = liga_nombre

        await editar_mensaje(
            query,
            texto_menu_liga(context),
            teclado_menu_liga(),
        )

    except Exception:
        logger.exception("ERROR ELEGIR LIGA")

        await editar_mensaje(
            query,
            "❌ No se pudo seleccionar la liga.",
        )


# ============================================================
# COMPROBAR LIGA ACTIVA
# ============================================================

async def comprobar_liga(update, context):
    liga_id = context.user_data.get("liga")

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

    return int(liga_id)


# ============================================================
# CONSTRUIR INFORME
# ============================================================

def construir_texto_informe(report):
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
            f"🟢 Compras: {formatear_dinero(compras)}\n"
            f"🔴 Ventas: {formatear_dinero(ventas)}\n"
            f"💰 Saldo: {formatear_dinero(saldo)}\n"
            f"💵 Puja máxima: {formatear_dinero(puja_maxima)}\n\n"
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


# ============================================================
# INFORME
# ============================================================

async def informe(update, context):
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

        texto = construir_texto_informe(
            report
        )

        botones = teclado_volver_principal()

        if len(texto) <= MAX_TELEGRAM:
            await mensaje_carga.edit_text(
                texto,
                reply_markup=botones,
            )

        else:
            await mensaje_carga.delete()

            partes = [
                texto[i:i + MAX_TELEGRAM]
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
        logger.exception("ERROR INFORME")

        await update.message.reply_text(
            f"Error calculando informe:\n{exc}"
        )


# ============================================================
# ENVIAR MOVIMIENTOS
# ============================================================

async def enviar_movimientos(
    update,
    titulo,
    movimientos,
):
    """Envía movimientos históricos en uno o varios mensajes."""

    if not movimientos:
        texto = (
            f"{titulo}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos."
        )

        if update.message is not None:
            return [
                await update.message.reply_text(
                    texto
                )
            ]

        if update.callback_query is not None:
            return [
                await update.callback_query.message.reply_text(
                    texto
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
            movimiento.get("player_id"),
            movimiento.get(
                "player_name",
                "Jugador",
            ),
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
            botones_actuales.append(
                [boton]
            )

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


# ============================================================
# MERCADO ACTUAL DE HOY
# ============================================================

async def enviar_mercado_hoy(
    update,
    datos,
):
    """
    Muestra el selector de tipos de venta del mercado actual.

    No muestra todavía los jugadores.

    El usuario puede elegir:
    - Jugadores en Venta Sistema.
    - Jugadores en Venta Miembros.
    """

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


def _normalizar_posicion(valor):
    """
    Normaliza las posiciones de Biwenger a:

    DL = delantero
    MC = centrocampista
    DF = defensa
    PT = portero
    """

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


def _posicion_venta(venta):
    """
    Obtiene la posición desde la venta.

    Primero intenta encontrarla dentro del objeto original
    devuelto por /market.

    Si no está disponible, utiliza la ficha cacheada del jugador.
    """

    sale = (
        venta.get("sale")
        if isinstance(venta, dict)
        else None
    )

    if isinstance(sale, dict):
        player = sale.get(
            "player"
        )

        if isinstance(player, dict):
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
            venta.get("player_id")
        )
    except Exception:
        jugador = None

    if isinstance(jugador, dict):
        datos = jugador.get(
            "datos"
        )

        if isinstance(datos, dict):
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


def _orden_posicion(posicion):
    """
    Orden solicitado:

    DL
    MC
    DF
    PT
    """

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
    """
    Ordena los jugadores por posición:

    DL -> MC -> DF -> PT

    Dentro de cada posición:
    nombre alfabético.
    """

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


async def mostrar_lista_mercado_hoy(
    query,
    datos,
    tipo,
):
    """
    Edita el mismo mensaje mostrando:

    - Sistema
    - Miembros
    """

    if tipo == "sistema":
        titulo = (
            "🤖 JUGADORES EN VENTA — SISTEMA"
        )

        ventas = datos.get(
            "jugadores_sistema",
            [],
        )

    else:
        titulo = (
            "👤 JUGADORES EN VENTA — MIEMBROS"
        )

        ventas = datos.get(
            "jugadores_managers",
            [],
        )

    if not isinstance(
        ventas,
        list,
    ):
        ventas = []

    ordenadas = _ordenar_ventas_por_posicion(
        ventas
    )

    lineas = [
        titulo,
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    if not ordenadas:
        lineas.append(
            "No hay jugadores en venta."
        )

    else:
        posicion_actual = None

        for venta, posicion in ordenadas:

            if posicion != posicion_actual:

                if posicion_actual is not None:
                    lineas.append("")

                lineas.append(
                    f"📌 {posicion}"
                )

                lineas.append("")

                posicion_actual = posicion

            nombre = venta.get(
                "player_name",
                "Jugador desconocido",
            )

            equipo = venta.get(
                "team",
                "?",
            )

            precio = formatear_dinero(
                venta.get(
                    "price",
                    0,
                )
            )

            until_datetime = venta.get(
                "until_datetime"
            )

            user_name = venta.get(
                "user_name"
            )

            lineas.append(
                f"⚽ {nombre} [{equipo}]"
            )

            lineas.append(
                f"💰 Precio: {precio}"
            )

            if tipo == "miembros" and user_name:
                lineas.append(
                    f"👤 Vendedor: {user_name}"
                )

            if until_datetime is not None:
                try:
                    lineas.append(
                        "⏳ Termina: "
                        + until_datetime.strftime(
                            "%H:%M"
                        )
                    )
                except Exception:
                    pass

            lineas.append("")

    texto = "\n".join(
        lineas
    ).rstrip()

    if len(texto) > MAX_TELEGRAM:
        texto = (
            texto[:MAX_TELEGRAM - 30].rstrip()
            + "\n\n…"
        )

    await editar_mensaje(
        query,
        texto,
        teclado_lista_mercado_hoy(),
    )


# ============================================================
# MENSAJE DE SUBMENU DESPUÉS DE RESULTADOS
# ============================================================

async def enviar_submenu_mercado(
    update,
):
    """
    Envía el submenu como mensaje nuevo después de un resultado.

    Se mantiene este comportamiento para Mercado completo,
    Mercado 24h y las funciones antiguas.
    """

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
            texto = (
                "🔄 MERCADO COMPLETO\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Sin movimientos."
            )

            if update.message is not None:
                await update.message.reply_text(
                    texto
                )
            else:
                await update.callback_query.message.reply_text(
                    texto
                )

            await enviar_submenu_mercado(
                update
            )

            return

        from biwenger import _nombre_fecha

        for clave in orden:

            if clave == "desconocida":
                titulo = (
                    "📅 FECHA DESCONOCIDA"
                )
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

        await enviar_submenu_mercado(
            update
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
# MERCADO DE HOY
# ============================================================

async def mercadohoy(
    update,
    context,
):
    """
    Mercado actual de Biwenger.

    Consulta /api/v2/market mediante
    obtener_mercado_hoy_datos().

    No utiliza el historial /board.

    Ahora muestra primero un submenu:
    - Jugadores en Venta Sistema
    - Jugadores en Venta Miembros
    """

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


# ============================================================
# MERCADO 24H
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
                    texto
                )

            else:
                await update.callback_query.message.reply_text(
                    texto
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


# ============================================================
# BOTONES DE NAVEGACIÓN POR FECHA
# ============================================================

def construir_botones_dias(
    liga_id,
    miembro_id,
    indice,
    total_dias,
    orden,
    timestamps,
    movimientos,
):
    botones = []

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
            botones.append(
                [boton]
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

    if indice < total_dias - 1:

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
            await editar_mensaje(
                query,
                (
                    f"🧑‍💼 MERCADO — {nombre_miembro}\n"
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
                    ],
                    [
                        InlineKeyboardButton(
                            "◀️ Volver a Mercado",
                            callback_data=(
                                "menu:mercado"
                            ),
                        )
                    ],
                ]),
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

        texto = construir_mensaje_dia_miembro(
            nombre_miembro,
            grupos,
            orden,
            timestamps,
            indice,
        )

        if len(texto) > MAX_TELEGRAM:
            texto = (
                texto[
                    :MAX_TELEGRAM - 50
                ]
                + "\n\n…"
            )

        teclado = construir_botones_dias(
            liga_id,
            miembro_id,
            indice,
            len(orden),
            orden,
            timestamps,
            movimientos,
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


# ============================================================
# SELECTOR DE MIEMBROS
# ============================================================

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
        partes = query.data.split(":")

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
            or int(liga_actual) != liga_id
        ):
            raise ValueError(
                "La liga seleccionada ya no coincide."
            )

        await editar_mensaje(
            query,
            "🔄 Cargando movimientos...",
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

        await editar_mensaje(
            query,
            "❌ No se pudieron obtener los movimientos del miembro.",
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
        partes = query.data.split(":")

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

        liga_actual = (
            context.user_data.get(
                "liga"
            )
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

        await editar_mensaje(
            query,
            "❌ No se pudo cambiar de día.",
        )


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
        partes = query.data.split(":")

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
            "❌ No se pudo volver a la selección de miembros.",
        )


# ============================================================
# FICHA DEL JUGADOR
# ============================================================

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
            f"💰 Precio: {formatear_dinero(precio)}\n"
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
                "❌ No se pudo obtener la ficha del jugador.",
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


# ============================================================
# CALLBACKS DEL MENÚ PRINCIPAL
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

                await editar_mensaje(
                    query,
                    texto,
                    teclado_volver_principal(),
                )

            else:

                await editar_mensaje(
                    query,
                    "📊 INFORME DE MANAGERS\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "El informe es demasiado largo para mostrarse en una sola pantalla.",
                )

                partes = [
                    texto[i:i + MAX_TELEGRAM]
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
                    reply_markup=teclado_volver_principal(),
                )

        elif accion == "mercado":

            await mostrar_submenu_mercado(
                update,
                context,
                editar=True,
            )

        elif accion == "principal":

            await editar_mensaje(
                query,
                texto_menu_liga(context),
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


# ============================================================
# CALLBACKS DEL SUBMENÚ DE MERCADO
# ============================================================

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

            await editar_mensaje(
                query,
                "🔄 MERCADO COMPLETO\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Cargando mercado...",
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

                await query.message.reply_text(
                    "🔄 MERCADO COMPLETO\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Sin movimientos."
                )

            else:

                from biwenger import _nombre_fecha

                for clave in orden:

                    if clave == "desconocida":
                        titulo = (
                            "📅 FECHA DESCONOCIDA"
                        )
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

            await enviar_submenu_mercado(
                update
            )

        elif accion == "hoy":

            await editar_mensaje(
                query,
                "📅 MERCADO — HOY\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Cargando mercado...",
            )

            datos = obtener_mercado_hoy_datos(
                liga_id
            )

            await enviar_mercado_hoy(
                update,
                datos,
            )

        elif accion == "24h":

            await editar_mensaje(
                query,
                "⏱️ MERCADO — 24H\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Cargando mercado...",
            )

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

                await query.message.reply_text(
                    titulo
                    + "\n"
                    + "━━━━━━━━━━━━━━━━━━━━\n\n"
                    + "Sin movimientos."
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

        elif accion == "miembro":

            await mostrar_selector_miembros(
                query,
                liga_id,
            )

        elif accion == "principal":

            await editar_mensaje(
                query,
                texto_menu_liga(context),
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


# ============================================================
# CALLBACKS DEL MERCADO ACTUAL
# ============================================================

async def mercado_hoy_callback(
    update,
    context,
):
    query = update.callback_query

    await query.answer()

    try:
        partes = query.data.split(
            ":",
            1,
        )

        if len(partes) != 2:
            raise ValueError(
                "Callback de mercado de hoy inválido"
            )

        tipo = partes[1]

        if tipo not in (
            "sistema",
            "miembros",
        ):
            raise ValueError(
                "Tipo de mercado de hoy inválido"
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

        # Se vuelve a consultar /market para que la información
        # sea la correspondiente al momento de pulsar el botón.

        await editar_mensaje(
            query,
            "📅 MERCADO — HOY\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Cargando jugadores...",
        )

        datos = obtener_mercado_hoy_datos(
            int(liga_id)
        )

        await mostrar_lista_mercado_hoy(
            query,
            datos,
            tipo,
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
        .token(
            TELEGRAM_TOKEN
        )
        .build()
    )

    # --------------------------------------------------------
    # COMANDOS
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

    # --------------------------------------------------------
    # BOTONES DE LIGA
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            elegir_liga,
            pattern=r"^liga:",
        )
    )

    # --------------------------------------------------------
    # MENÚ PRINCIPAL
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            menu_callback,
            pattern=r"^menu:",
        )
    )

    # --------------------------------------------------------
    # SUBMENÚ MERCADO
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            mercado_callback,
            pattern=r"^mercado:",
        )
    )

    # --------------------------------------------------------
    # MIEMBROS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MERCADO ACTUAL
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            mercado_hoy_callback,
            pattern=r"^mercadohoy:",
        )
    )

    # --------------------------------------------------------
    # FICHA JUGADOR
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            ficha_jugador,
            pattern=r"^jugador:",
        )
    )

    # --------------------------------------------------------
    # ERRORES
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