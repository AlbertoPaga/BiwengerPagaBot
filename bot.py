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
    obtener_mercado_hoy_datos,
    obtener_miembros_liga,
    obtener_mercado_miembro_datos,
    obtener_ficha_jugador,
)

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(
    __name__
)

MAX_TELEGRAM = 4000


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
            float(timestamp)
        )

        return fecha.strftime(
            "%d/%m/%y"
        )

    except Exception:
        return "??/??/??"


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
                "🙋 Tus jugadores en venta",
                callback_data="mercadohoy:propios",
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
    posicion_actual,
):
    """
    Botones de paginación directa por posición.

    Cada botón lleva directamente a la posición seleccionada,
    sin depender de anterior/siguiente ni del orden de las
    posiciones que tengan jugadores.
    """
    botones = []

    nombres = {
        "DL": "DL",
        "MC": "MC",
        "DF": "DF",
        "PT": "PT",
    }

    fila = []

    for posicion in ("DL", "MC", "DF", "PT"):
        prefijo = "🔘 " if posicion == posicion_actual else ""

        fila.append(
            InlineKeyboardButton(
                prefijo + nombres[posicion],
                callback_data=(
                    f"mercadohoydia:{tipo}:{posicion}"
                ),
            )
        )

    botones.append(fila)

    botones.append([
        InlineKeyboardButton(
            "◀️ Volver a Mercado de Hoy",
            callback_data="mercado:hoy",
        )
    ])

    return InlineKeyboardMarkup(botones)


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
            teclado_volver_principal()
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
                InlineKeyboardMarkup(
                    botones_actuales
                )
                if botones_actuales
                else None
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
            InlineKeyboardMarkup(
                botones_actuales
            )
            if botones_actuales
            else None
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


def _agrupar_ventas_por_posicion(ventas):
    posiciones = {
        "DL": [],
        "MC": [],
        "DF": [],
        "PT": [],
    }

    for venta, posicion in _ordenar_ventas_por_posicion(ventas):
        if posicion in posiciones:
            posiciones[posicion].append(venta)

    return [
        (posicion, posiciones[posicion])
        for posicion in ("DL", "MC", "DF", "PT")
        if posiciones[posicion]
    ]


def _texto_ofertas_venta(venta):
    numero = venta.get("numero_ofertas", 0)
    mayor = venta.get("mayor_oferta")
    ofertante = venta.get("mayor_oferta_user_name")

    if not numero:
        return "📨 Ofertas: ninguna"

    lineas = [
        f"📨 Ofertas: {numero}",
    ]

    if mayor is not None:
        texto = f"💎 Mayor oferta: {formatear_dinero(mayor)}"
        if ofertante:
            texto += f" — {ofertante}"
        lineas.append(texto)

    return "\n".join(lineas)


async def mostrar_lista_mercado_hoy(
    query,
    datos,
    tipo,
    indice=0,
):
    configuracion = {
        "sistema": (
            "🤖 JUGADORES EN VENTA — SISTEMA",
            datos.get("jugadores_sistema", []),
        ),
        "miembros": (
            "👤 JUGADORES EN VENTA — MIEMBROS",
            datos.get("jugadores_managers", []),
        ),
        "propios": (
            "🙋 TUS JUGADORES EN VENTA",
            datos.get("jugadores_propios", []),
        ),
    }

    if tipo not in configuracion:
        raise ValueError("Tipo de mercado de hoy inválido")

    titulo, ventas = configuracion[tipo]

    if not isinstance(ventas, list):
        ventas = []

    grupos = _agrupar_ventas_por_posicion(ventas)

    if not grupos:
        await editar_mensaje(
            query,
            titulo
            + "\n"
            + "━━━━━━━━━━━━━━━━━━━━\n\n"
            + "No hay jugadores en venta.",
            teclado_lista_mercado_hoy(tipo, "DL"),
        )
        return

    posiciones_disponibles = [
        posicion
        for posicion, _ventas in grupos
    ]

    # El callback puede venir con una posición concreta (DL/MC/DF/PT).
    # Mantenemos también compatibilidad con el índice numérico antiguo.
    if isinstance(indice, str):
        posicion = indice.upper()
        if posicion not in {"DL", "MC", "DF", "PT"}:
            posicion = posiciones_disponibles[0]
    else:
        indice = max(0, min(indice, len(grupos) - 1))
        posicion = grupos[indice][0]

    ventas_posicion = next(
        (
            ventas
            for posicion_grupo, ventas in grupos
            if posicion_grupo == posicion
        ),
        [],
    )

    nombres_posicion = {
        "DL": "DELANTEROS",
        "MC": "MEDIOCENTROS",
        "DF": "DEFENSAS",
        "PT": "PORTEROS",
    }

    lineas = [
        titulo,
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📌 {nombres_posicion[posicion]}",
        "",
    ]

    for venta in ventas_posicion:
        nombre = venta.get("player_name", "Jugador desconocido")
        equipo = venta.get("team", "?")
        precio = formatear_dinero(venta.get("price", 0))

        lineas.append(f"⚽ {nombre} [{equipo}]")
        lineas.append(f"💰 Precio: {precio}")

        if tipo == "miembros":
            vendedor = venta.get("user_name")
            if vendedor:
                lineas.append(f"👤 Vendedor: {vendedor}")

        if tipo == "propios":
            lineas.append(_texto_ofertas_venta(venta))

        until_datetime = venta.get("until_datetime")
        if until_datetime is not None:
            try:
                lineas.append(
                    "⏳ Termina: "
                    + until_datetime.strftime("%H:%M")
                )
            except Exception:
                pass

        lineas.append("")

    texto = "\n".join(lineas).rstrip()

    if len(texto) > MAX_TELEGRAM:
        texto = texto[:MAX_TELEGRAM - 30].rstrip() + "\n\n…"

    await editar_mensaje(
        query,
        texto,
        teclado_lista_mercado_hoy(
            tipo,
            posicion,
        ),
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
            botones.append([
                boton
            ])

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
                len(orden),
                orden,
                timestamps,
                movimientos,
            )
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

        await editar_mensaje(
            query,
            "🔄 Cargando movimientos...",
        )

        datos = (
            obtener_mercado_miembro_datos(
                liga_id,
                miembro_id,
            )
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
        return InlineKeyboardMarkup([])

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📌 Fijar jugador",
                callback_data=(
                    f"fijar:{player_id}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "◀️ Anterior",
                callback_data=(
                    "jugador_anterior"
                ),
            )
        ],
    ])


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

        context.user_data[
            "jugador_anterior_texto"
        ] = (
            query.message.text or ""
        )

        context.user_data[
            "jugador_anterior_markup"
        ] = query.message.reply_markup

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


async def fijar_jugador(
    update,
    context,
):
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

        await query.message.reply_text(
            "◀️ Anterior",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "◀️ Anterior",
                        callback_data=(
                            "jugador_anterior"
                        ),
                    )
                ]
            ]),
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

        texto = context.user_data.get(
            "jugador_anterior_texto"
        )

        markup = context.user_data.get(
            "jugador_anterior_markup"
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

                await editar_mensaje(
                    query,
                    texto,
                    teclado_volver_principal(),
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


def construir_botones_dia_mercado_completo(
    datos,
    indice,
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
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "◀️ Volver a Mercado",
                    callback_data=(
                        "menu:mercado"
                    ),
                )
            ]
        ])

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

        if boton:
            botones.append([
                boton
            ])

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

    return InlineKeyboardMarkup(
        botones
    )


async def mostrar_dia_mercado_completo(
    query,
    context,
    indice,
    datos=None,
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
        )
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

    except Exception:
        logger.exception(
            "ERROR CAMBIAR DÍA MERCADO COMPLETO"
        )

        await editar_mensaje(
            query,
            "❌ No se pudo cambiar de día.",
            teclado_submenu_mercado(),
        )


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
                    InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "◀️ Volver a Mercado",
                                callback_data=(
                                    "menu:mercado"
                                ),
                            )
                        ]
                    ]),
                )

            else:

                botones = []

                for movimiento in (
                    movimientos_datos
                ):
                    ficha = (
                        obtener_ficha_jugador(
                            movimiento.get(
                                "player_id"
                            )
                        )
                        or {}
                    )

                    botones.append([
                        InlineKeyboardButton(
                            (
                                f"⚽ "
                                f"{movimiento.get('player_name', 'Jugador')} "
                                f"[{ficha.get('equipo', '?')}] "
                                f"({ficha.get('posicion', '?')})"
                            ),
                            callback_data=(
                                f"jugador:"
                                f"{movimiento.get('player_id')}"
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
                    InlineKeyboardMarkup(
                        botones
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


async def mercado_hoy_callback(
    update,
    context,
):
    query = update.callback_query
    await query.answer()

    try:
        partes = query.data.split(":")

        if len(partes) < 2:
            raise ValueError("Callback de mercado de hoy inválido")

        tipo = partes[1]
        if tipo not in ("sistema", "miembros", "propios"):
            raise ValueError("Tipo de mercado de hoy inválido")

        posicion = "DL"
        if len(partes) == 3:
            posicion = partes[2].upper()

        if posicion not in ("DL", "MC", "DF", "PT"):
            raise ValueError("Posición de mercado de hoy inválida")

        liga_id = context.user_data.get("liga")
        if not liga_id:
            await query.answer(
                "Primero selecciona una liga.",
                show_alert=True,
            )
            return

        await editar_mensaje(
            query,
            "📅 MERCADO — HOY\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Cargando jugadores...",
        )

        datos = obtener_mercado_hoy_datos(int(liga_id))

        await mostrar_lista_mercado_hoy(
            query,
            datos,
            tipo,
            posicion,
        )

    except Exception:
        logger.exception("ERROR MERCADO HOY CALLBACK")
        await editar_mensaje(
            query,
            "❌ No se pudo cargar el mercado de hoy.",
            teclado_mercado_hoy(),
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
            mercado_hoy_callback,
            pattern=r"^mercadohoydia:",
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
