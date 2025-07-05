from telethon import TelegramClient, events
from models import Chat, Module, ChatModule
from json import loads, decoder, dumps
from modules import extract_chat_id


def set_nested(d: dict, keys: list[str], value):
    """Устанавливает значение по вложенному пути в словаре"""
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


async def process_message(event: events.NewMessage, client: TelegramClient):
    message = event.raw_text
    chat_id = extract_chat_id(event)
    from_my = event.message.out

    if not from_my:
        return

    if message.strip().startswith("/init"):
        return await process_init_message(event=event, client=client)
    elif message.strip().startswith("/modreg"):
        return await process_modreg_message(event=event, client=client)
    elif message.strip().startswith("/config"):
        return await process_config_message(event=event, client=client)
    elif message.strip().startswith("/modprobe"):
        return await process_modprobe_message(event=event, client=client)
    elif message.strip().startswith("/rmmod"):
        return await process_rmmode_message(event=event, client=client)
    elif message.strip().startswith("/lsmod"):
        return await process_lsmod_message(event=event, client=client)
    elif message.strip().startswith("/modinfo"):
        return await process_modinfo_message(event=event, client=client)
    elif message.strip().startswith("/modcfg"):
        return await process_modcfg_message(event=event, client=client)


async def process_init_message(event: events.NewMessage, client: TelegramClient):
    chat_id = extract_chat_id(event)
    msg = await client.send_message(
        chat_id,
        f"Запрос на инициализацию чата({chat_id}) принят.",
        reply_to=event.message,
    )
    user, created = await Chat.get_or_create(chat_id=chat_id)

    if created:
        await msg.edit(
            f"Запись для нового чата создана, чат {chat_id} добавлен под id: {user.id}"
        )
    else:
        await msg.edit(f"Такой чат уже({chat_id}) был зарегистрирован с id {user.id}")
    return


async def process_modreg_message(event: events.NewMessage, client: TelegramClient):
    chat_id = extract_chat_id(event)

    parts = event.raw_text.strip().split()
    if len(parts) < 3:
        await client.send_message(
            chat_id,
            f"Проверьте формат сообщения, требуется больше 3х частей({len(parts)}<3)",
            reply_to=event.message,
        )
        return

    msg = await client.send_message(
        chat_id, f"Обрабатываем запрос", reply_to=event.message
    )

    module_name = parts[1]
    description = " ".join(parts[2:])

    db_module = await Module.filter(name=module_name).first()

    if db_module is not None:
        await msg.edit(
            f"Модуль с именем {db_module.name} найден. Описание:\n```{db_module.description}```"
        )
        return

    module = await Module.create(name=module_name, description=description)

    await msg.edit(
        f"""Модуль был успешно создан\nid: ``` {module.id}```\nkey: ``` {module.key}```\n\n\nНе забудь про``` /modcfg {module_name} json config```и``` /config {module_name}.system.required_types [1,2,3] ```""")
    return


async def process_config_message(event: events.NewMessage, client: TelegramClient):
    chat_id = extract_chat_id(event)
    parts = event.raw_text.strip().split()

    if len(parts) <3:
        await client.send_message(
            chat_id,
            f"Неверный формат: требуется not <3",
            reply_to=event.message,
        )
        return
    
    config_path = parts[1].strip().split(".")
    payload = " ".join(parts[2:])

    if len(config_path) <2:
        await client.send_message(
            chat_id,
            f"Неверный формат команды, ожидается минимум 3 части после /config",
            reply_to=event.message,
        )
        return

    module_name, *path_parts = config_path
    msg = await client.send_message(
        chat_id, f"Обрабатываем запрос...", reply_to=event.message
    )

    db_module = await Module.filter(name=module_name).first()
    if db_module is None:
        await msg.edit(f"Модуль `{module_name}` не найден.")
        return
    
    chat = await Chat.filter(chat_id=chat_id).first()
    if chat is None:
        await msg.edit(
            f"Кажется чат с id: {chat_id} не зарегестрирован.\n забайтили, я уже проверил наличие модуля"
        )
        return

    if path_parts[0] == "system":
        if len(path_parts) < 2:
            await msg.edit(
                "Для системного конфига необходимо указать 4-ю часть: например `/config.module.system.required_types`"
            )
            return

        key = path_parts[1]
        if key == "required_types":
            try:
                types_required = loads(payload)
                required_types = [int(i) for i in types_required]
            except (decoder.JSONDecodeError, ValueError):
                await msg.edit("Ожидается JSON-массив целых чисел.")
                return

            db_module.required_msgs = required_types
            await db_module.save()
            await msg.edit("Системный конфиг успешно обновлён!")
            return
        elif key == "system":
            try:
                system_values = loads(payload)
            except decoder.JSONDecodeError as e:
                await msg.edit(f"ЖСОНКУ ХОЧУ {e}")
                return
            db_module.system_config = system_values
            await db_module.save()
            await msg.edit("Обновил конфиг модуля")
            return
        else:
            await msg.edit(f"Неизвестный системный ключ: `{key}`")
            return

    db_chatmodule = await ChatModule.filter(chat=chat, module=db_module).first()
    if db_chatmodule is None:
        await msg.edit("Модуль не подключён к текущему чату.")
        return

    try:
        parsed_payload = loads(payload)
    except decoder.JSONDecodeError:
        await msg.edit("Невалидный JSON payload.")
        return

    config = db_chatmodule.config_json or {}
    set_nested(config, path_parts, parsed_payload)

    db_chatmodule.config_json = config
    await db_chatmodule.save()
    await msg.edit("Конфигурация успешно обновлена!")


async def process_modprobe_message(event: events.NewMessage, client: TelegramClient):
    chat_id = extract_chat_id(event)
    parts = event.raw_text.strip().split()

    if len(parts) != 2:
        await client.send_message(
            chat_id,
            f"Проверьте формат сообщения, требуется больше ровно 2 части({len(parts)}!=2)",
            reply_to=event.message,
        )
        return

    target_name = parts[1]

    msg = await client.send_message(
        chat_id, f"Обрабатываем запрос", reply_to=event.message
    )

    target = await Module.filter(name=target_name).first()
    if target is None:
        await msg.edit(f"Модуль с именем {target_name} не найден.")
        return

    chat = await Chat.filter(chat_id=chat_id).first()
    if chat is None:
        await msg.edit(
            f"Кажется чат с id: {chat_id} не зарегестрирован.\n забайтили, я уже проверил наличие модуля"
        )
        return

    chatmodule, created = await ChatModule.get_or_create(module=target, chat=chat, config_json=target.default_config_json)
    if created:
        await msg.edit(f"Модуль успешно загружен в ядро!")
    else:
        await msg.edit(f"Модуль уже был подключен.")

    return


async def process_rmmode_message(event: events.NewMessage, client: TelegramClient):
    chat_id = extract_chat_id(event)
    parts = event.raw_text.strip().split()

    if len(parts) != 2:
        await client.send_message(
            chat_id,
            f"Проверьте формат сообщения, требуется больше ровно 2 части({len(parts)}!=2)",
            reply_to=event.message,
        )
        return

    target_name = parts[1]

    msg = await client.send_message(
        chat_id, f"Обрабатываем запрос", reply_to=event.message
    )

    target = await Module.filter(name=target_name).first()
    if target is None:
        await msg.edit(f"Модуль с именем {target_name} не найден.")
        return

    chat = await Chat.filter(chat_id=chat_id).first()
    if chat is None:
        await msg.edit(
            f"Кажется чат с id: {chat_id} не зарегестрирован.\n забайтили, я уже проверил наличие модуля"
        )
        return

    chatmodule = await ChatModule.filter(chat=chat, module=target).first()
    if not chatmodule:
        await msg.edit(f"Такой модуль не загружен в ядро чата.")
        return
    await chatmodule.delete()
    await msg.edit(f"Модуль выгружен.")
    return


async def process_lsmod_message(event: events.NewMessage, client: TelegramClient):
    chat_id = extract_chat_id(event)

    msg = await client.send_message(
        chat_id, f"Обрабатываем запрос", reply_to=event.message
    )

    chat = await Chat.filter(chat_id=chat_id).first()
    if chat is None:
        await msg.edit(f"Кажется чат id: {chat_id} не зарегестрирован.")
        return

    chatmodules = await ChatModule.filter(chat=chat).prefetch_related("module")
    modules = [cm.module.name for cm in chatmodules]
    await msg.edit("Подгружено:\n" + "\n".join(modules))
    return


async def process_modinfo_message(event: events.NewMessage, client: TelegramClient):
    chat_id = extract_chat_id(event)
    parts = event.raw_text.strip().split()

    if len(parts) != 2:
        await client.send_message(
            chat_id,
            f"Проверьте формат сообщения, требуется ровно 2 части({len(parts)}!=2)",
            reply_to=event.message,
        )
        return

    target_name = parts[1]

    msg = await client.send_message(
        chat_id, f"Обрабатываем запрос", reply_to=event.message
    )

    target = await Module.filter(name=target_name).first()
    if target is None:
        await msg.edit(f"Модуль с именем {target_name} не найден.")
        return

    await msg.edit(
        f"Модуль с именем {target_name} найден.\n``` {target.description}```"
    )
    return


async def process_modcfg_message(event: events.NewMessage, client: TelegramClient):
    chat_id = extract_chat_id(event)
    parts = event.raw_text.strip().split()

    if len(parts) <3:
        await client.send_message(
            chat_id,
            f"Проверьте формат сообщения, требуется >3 части({len(parts)}<3)",
            reply_to=event.message,
        )
        return

    target_name = parts[1]

    msg = await client.send_message(
        chat_id, f"Обрабатываем запрос", reply_to=event.message
    )

    target = await Module.filter(name=target_name).first()
    if target is None:
        await msg.edit(f"Модуль с именем {target_name} не найден.")
        return
    
    config = " ".join(parts[2:])
    try:
        config = loads(config)
    except decoder.JSONDecodeError as e:
        await msg.edit(f"Проверь блин коректность жсонки, тут кажется чёт не так.\n``` {e}```")
        return
    
    target.default_config_json = config
    await target.save()
    await msg.edit(f"Новое значение стандартного конфига сохранено.\n``` {dumps(config)}```")

