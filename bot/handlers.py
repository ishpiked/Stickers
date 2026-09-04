import os
import uuid
import traceback

from telegram import Update, InputSticker
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

from bot.config import BOT_USERNAME, ADMIN_IDS, MAX_STATIC_BYTES, MAX_VIDEO_BYTES
from bot.keyboards import crop_choice_keyboard, preview_keyboard, emoji_keyboard, subscribe_keyboard, start_keyboard, help_keyboard, packs_keyboard, pack_detail_keyboard
from bot import state, media
from bot.logger import log
from bot.subscription import is_subscribed


# ---------- gates shared by user facing handlers ----------

async def _blocked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id

    if state.is_banned(user_id):
        return True

    if not await is_subscribed(context.bot, user_id):
        channel = state.get_settings()["force_sub_channel"]
        clean = channel.lstrip("@")
        await update.effective_message.reply_text(
            f"Join {clean} to continue. Tap below to verify.",
            reply_markup=subscribe_keyboard(channel),
        )
        return True

    return False


async def checksub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if await is_subscribed(context.bot, user_id):
        await query.answer("Verified")
        await query.edit_message_text("Verified. Send a photo, GIF or video to continue.")
    else:
        await query.answer("Not verified yet. Please try again.", show_alert=True)


# ---------- user commands ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.remember_chat(update.effective_chat.id)
    if await _blocked(update, context):
        return
    settings = state.get_settings()
    if settings["start_image"]:
        await update.message.reply_photo(settings["start_image"], caption=settings["start_text"], reply_markup=start_keyboard())
    else:
        await update.message.reply_text(settings["start_text"], reply_markup=start_keyboard())


async def newpack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _blocked(update, context):
        return
    if not context.args:
        await update.message.reply_text("Use: /newpack [name]")
        return
    clean = "_".join(context.args).strip().lower()
    pack_name = f"{clean}_by_{BOT_USERNAME.lower()}"
    user_id = update.effective_user.id
    state.set_active_pack(user_id, pack_name)
    state.add_user_pack(user_id, pack_name)
    display = pack_name.split("_by_")[0].replace("_", " ")
    await update.message.reply_text(
        f"Pack set to {display}. Now send a photo, GIF or video."
    )
    await log(context.bot, f"New pack {pack_name} by user {user_id}")


async def mypacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _blocked(update, context):
        return
    user_id = update.effective_user.id
    packs = state.list_user_packs(user_id)
    visible = [p for p in packs if not state.is_pack_hidden(user_id, p)]
    if not visible:
        await update.message.reply_text("No packs yet. Use /newpack [name] to start.")
        return
    lines = []
    for p in visible:
        try:
            s = await context.bot.get_sticker_set(p)
            display = p.split("_by_")[0].replace("_", " ")
            lines.append(f"{display} : {len(s.stickers)}/120")
        except BadRequest:
            display = p.split("_by_")[0].replace("_", " ")
            lines.append(f"{display} : gone")
    await update.message.reply_text("Your packs:\n" + "\n".join(lines) + "\n\nUse /usepack [name] to switch.")


async def usepack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _blocked(update, context):
        return
    if not context.args:
        await update.message.reply_text("Use: /usepack [name]")
        return
    pack_name = context.args[0]
    user_id = update.effective_user.id
    if pack_name not in state.list_user_packs(user_id) and not state.is_owner_or_coowner(user_id, pack_name):
        await update.message.reply_text("This pack is not in your list.")
        return
    state.set_active_pack(user_id, pack_name)
    display = pack_name.split("_by_")[0].replace("_", " ")
    await update.message.reply_text(f"Active pack set to {display}.")


async def renamepack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _blocked(update, context):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Use: /renamepack [name] [new title]")
        return
    pack_name, new_title = context.args[0], " ".join(context.args[1:])
    user_id = update.effective_user.id
    if pack_name not in state.list_user_packs(user_id) and not state.is_owner_or_coowner(user_id, pack_name):
        await update.message.reply_text("This pack is not yours.")
        return
    try:
        await context.bot.set_sticker_set_title(name=pack_name, title=new_title)
        await update.message.reply_text("Renamed.")
    except BadRequest as e:
        await update.message.reply_text(f"Could not rename: {e}")


async def removesticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _blocked(update, context):
        return
    replied = update.message.reply_to_message
    if not replied or not replied.sticker:
        await update.message.reply_text("Reply to a sticker with /removesticker")
        return
    set_name = replied.sticker.set_name
    user_id = update.effective_user.id
    if set_name not in state.list_user_packs(user_id) and user_id not in ADMIN_IDS:
        await update.message.reply_text("This pack is not yours.")
        return
    try:
        await context.bot.delete_sticker_from_set(sticker=replied.sticker.file_id)
        await update.message.reply_text("Removed.")
        await log(context.bot, f"Sticker removed from {set_name} by user {user_id}")
    except BadRequest as e:
        await update.message.reply_text(f"Could not remove: {e}")


def _get_help_text(user_id: int) -> str:
    is_admin = user_id in ADMIN_IDS
    text = (
        "Xtickerz Help.\n\n"
        "Xtickerz converts photos, GIFs and videos into Telegram stickers.\n\n"
        "Commands:\n"
        " /start : view welcome message\n"
        " /newpack [name] : create a new pack\n"
        " /usepack [name] : switch to your pack\n"
        " /mypacks : list your packs\n"
        " /renamepack [name] [new title] : rename a pack you own\n"
        " /removesticker : reply to a sticker to remove it\n"
        " /cancel : cancel current action\n"
        " /help : view this message\n\n"
        "Send any photo, GIF or video and it will be prepared as a sticker for your active pack.\n"
    )
    if is_admin:
        text += (
            "\nAdmin:\n"
            " /ban [id] : ban a user\n"
            " /unban [id] : unban a user\n"
            " /stats : view sticker count\n"
            " /health : check service status\n"
            " /broadcast [text] : send message to all chats\n"
            " /settings : view settings\n"
            " /setstarttext [text] : update welcome text\n"
            " /setstartimage : reply to a photo to update welcome image, use [none] to clear\n"
            " /setforcesub [channel or off] : set force join channel\n"
            " /setratelimit [n] : set hourly limit\n"
            " /resetsettings : reset to defaults\n"
        )
    return text


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = _get_help_text(update.effective_user.id)
    await update.message.reply_text(text, reply_markup=help_keyboard())


async def handle_help_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, action = query.data.split(":")
    user_id = query.from_user.id
    if state.is_banned(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    if action == "open":
        text = _get_help_text(user_id)
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=help_keyboard())
            else:
                await query.edit_message_text(text=text, reply_markup=help_keyboard())
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=help_keyboard())
    elif action == "back":
        settings = state.get_settings()
        text = settings["start_text"]
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=start_keyboard())
            else:
                await query.edit_message_text(text=text, reply_markup=start_keyboard())
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=start_keyboard())


# ---------- start extra buttons ----------

async def handle_start_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, action = query.data.split(":")
    user_id = query.from_user.id
    if state.is_banned(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    if action == "mypacks":
        packs = state.list_user_packs(user_id)
        visible = [p for p in packs if not state.is_pack_hidden(user_id, p)]
        if not visible:
            text = "You have no packs yet. Tap Create to make a new pack."
            try:
                if query.message.photo:
                    await query.edit_message_caption(caption=text, reply_markup=packs_keyboard([]))
                else:
                    await query.edit_message_text(text=text, reply_markup=packs_keyboard([]))
            except BadRequest:
                await query.edit_message_text(text=text, reply_markup=packs_keyboard([]))
            return
        text = "Your packs. Tap a pack to manage it."
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=packs_keyboard(visible))
            else:
                await query.edit_message_text(text=text, reply_markup=packs_keyboard(visible))
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=packs_keyboard(visible))
    elif action == "create":
        state.set_awaiting(user_id, "create_pack")
        text = "Send pack name for new pack. Use only letters and numbers."
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=help_keyboard())
            else:
                await query.edit_message_text(text=text, reply_markup=help_keyboard())
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=help_keyboard())
    elif action == "stats":
        packs = state.list_user_packs(user_id)
        total = len(packs)
        created = state.get_stat("stickers_created")
        active = state.get_active_pack(user_id) or "none"
        if active != "none":
            active = active.split("_by_")[0].replace("_", " ")
        text = f"Stats.\nPacks: {total}\nStickers created: {created}\nActive pack: {active}"
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=help_keyboard())
            else:
                await query.edit_message_text(text=text, reply_markup=help_keyboard())
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=help_keyboard())


async def handle_pack_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, pack_name = query.data.split(":", 2)
    user_id = query.from_user.id
    if state.is_banned(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    if not state.is_owner_or_coowner(user_id, pack_name):
        await query.answer("Not your pack.", show_alert=True)
        return
    is_hidden = state.is_pack_hidden(user_id, pack_name)
    try:
        s = await context.bot.get_sticker_set(pack_name)
        count = len(s.stickers)
        title = s.title
    except BadRequest:
        count = 0
        title = pack_name.split("_by_")[0].replace("_", " ")
    text = f"Pack: {title}\nStickers: {count}\nHidden: {'yes' if is_hidden else 'no'}"
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=text, reply_markup=pack_detail_keyboard(pack_name, is_hidden))
        else:
            await query.edit_message_text(text=text, reply_markup=pack_detail_keyboard(pack_name, is_hidden))
    except BadRequest:
        await query.edit_message_text(text=text, reply_markup=pack_detail_keyboard(pack_name, is_hidden))


async def handle_pack_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":", 2)
    _, action, pack_name = parts
    user_id = query.from_user.id
    if state.is_banned(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    if not state.is_owner_or_coowner(user_id, pack_name):
        await query.answer("Not your pack.", show_alert=True)
        return
    if action == "add":
        state.clear_awaiting(user_id)
        state.set_active_pack(user_id, pack_name)
        state.add_user_pack(user_id, pack_name)
        display = pack_name.split("_by_")[0].replace("_", " ")
        text = f"Active pack set to {display}. Send a photo, GIF or video to add stickers."
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=pack_detail_keyboard(pack_name, state.is_pack_hidden(user_id, pack_name)))
            else:
                await query.edit_message_text(text=text, reply_markup=pack_detail_keyboard(pack_name, state.is_pack_hidden(user_id, pack_name)))
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=pack_detail_keyboard(pack_name, state.is_pack_hidden(user_id, pack_name)))
    elif action == "rename":
        state.set_awaiting(user_id, "rename_pack", {"pack": pack_name})
        text = "Send new title for pack."
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=help_keyboard())
            else:
                await query.edit_message_text(text=text, reply_markup=help_keyboard())
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=help_keyboard())
    elif action == "frame":
        state.set_awaiting(user_id, "set_frame", {"pack": pack_name})
        text = "Send a photo to set as pack frame."
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=help_keyboard())
            else:
                await query.edit_message_text(text=text, reply_markup=help_keyboard())
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=help_keyboard())
    elif action == "stat":
        try:
            s = await context.bot.get_sticker_set(pack_name)
            count = len(s.stickers)
            title = s.title
        except BadRequest:
            count = 0
            title = pack_name.split("_by_")[0].replace("_", " ")
        coowners = state.list_coowners(pack_name)
        co_text = ", ".join(str(x) for x in coowners) if coowners else "none"
        owner_id = state.get_pack_owner(pack_name)
        owner_text = str(owner_id) if owner_id else "unknown"
        is_hidden = state.is_pack_hidden(user_id, pack_name)
        text = f"Pack stats.\nTitle: {title}\nStickers: {count}\nHidden: {'yes' if is_hidden else 'no'}\nOwner: {owner_text}\nCoowners: {co_text}"
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=pack_detail_keyboard(pack_name, is_hidden))
            else:
                await query.edit_message_text(text=text, reply_markup=pack_detail_keyboard(pack_name, is_hidden))
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=pack_detail_keyboard(pack_name, is_hidden))
    elif action == "transfer":
        if not state.is_original_owner(user_id, pack_name):
            await query.answer("Only the pack owner can transfer.", show_alert=True)
            return
        state.set_awaiting(user_id, "transfer_pack", {"pack": pack_name})
        text = "Send user id to give access to this pack."
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=help_keyboard())
            else:
                await query.edit_message_text(text=text, reply_markup=help_keyboard())
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=help_keyboard())
    elif action == "hide":
        is_hidden = state.is_pack_hidden(user_id, pack_name)
        if is_hidden:
            state.show_pack(user_id, pack_name)
            new_hidden = False
            text = "Pack is now visible."
        else:
            state.hide_pack(user_id, pack_name)
            new_hidden = True
            text = "Pack is now hidden."
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=pack_detail_keyboard(pack_name, new_hidden))
            else:
                await query.edit_message_text(text=text, reply_markup=pack_detail_keyboard(pack_name, new_hidden))
        except BadRequest:
            await query.edit_message_text(text=text, reply_markup=pack_detail_keyboard(pack_name, new_hidden))


async def handle_awaiting_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting = state.get_awaiting(user_id)
    if not awaiting:
        return False
    action = awaiting.get("action")
    data = awaiting.get("data", {})
    text = update.message.text.strip() if update.message.text else ""
    if action == "create_pack":
        if not text:
            await update.message.reply_text("Send a valid pack name.")
            return True
        clean = text.strip().lower().replace(" ", "_")
        if not clean.replace("_", "").isalnum():
            await update.message.reply_text("Pack name must use only letters and numbers.")
            return True
        if len(clean) < 2 or len(clean) > 30:
            await update.message.reply_text("Pack name must be 2 to 30 characters.")
            return True
        pack_name = f"{clean}_by_{BOT_USERNAME.lower()}"
        if pack_name in state.list_user_packs(user_id):
            await update.message.reply_text("You already have a pack with this name.")
            return True
        state.set_active_pack(user_id, pack_name)
        state.add_user_pack(user_id, pack_name)
        state.clear_awaiting(user_id)
        display = pack_name.split("_by_")[0].replace("_", " ")
        await update.message.reply_text(f"Pack created: {display}. It is now active. Send media to add stickers.", reply_markup=pack_detail_keyboard(pack_name, False))
        await log(context.bot, f"Pack created {pack_name} by user {user_id}")
        return True
    elif action == "rename_pack":
        pack_name = data.get("pack")
        if not pack_name or not text:
            await update.message.reply_text("Send a valid title.")
            return True
        try:
            await context.bot.set_sticker_set_title(name=pack_name, title=text)
            state.clear_awaiting(user_id)
            await update.message.reply_text("Pack renamed.", reply_markup=pack_detail_keyboard(pack_name, state.is_pack_hidden(user_id, pack_name)))
        except BadRequest as e:
            await update.message.reply_text(f"Could not rename: {e}")
        return True
    elif action == "transfer_pack":
        pack_name = data.get("pack")
        try:
            new_id = int(text)
        except ValueError:
            await update.message.reply_text("Send a valid user id.")
            return True
        state.add_coowner(pack_name, new_id)
        state.clear_awaiting(user_id)
        display = pack_name.split("_by_")[0].replace("_", " ")
        await update.message.reply_text(f"Access given to {new_id} for pack {display}.", reply_markup=pack_detail_keyboard(pack_name, state.is_pack_hidden(user_id, pack_name)))
        await log(context.bot, f"Pack {pack_name} shared to {new_id} by {user_id}")
        return True
    return False


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_awaiting_text(update, context):
        return


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.clear_awaiting(update.effective_user.id)
    await update.message.reply_text("Cancelled.", reply_markup=start_keyboard())


# ---------- media intake ----------

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.remember_chat(update.effective_chat.id)
    if await _blocked(update, context):
        return

    user_id = update.effective_user.id
    awaiting = state.get_awaiting(user_id)
    if awaiting and awaiting.get("action") == "set_frame":
        pack_name = awaiting["data"].get("pack")
        if not state.is_owner_or_coowner(user_id, pack_name):
            await update.message.reply_text("This pack is not yours.")
            state.clear_awaiting(user_id)
            return
        if not update.message.photo:
            await update.message.reply_text("Send a photo for frame.")
            return
        try:
            file = await update.message.photo[-1].get_file()
            local_path = media.tmp_path(".jpg")
            await file.download_to_drive(local_path)
            try:
                with open(local_path, "rb") as f:
                    await context.bot.set_sticker_set_thumbnail(name=pack_name, user_id=user_id, format="static", thumbnail=f)
            except BadRequest as e:
                if "format" in str(e).lower():
                    with open(local_path, "rb") as f:
                        await context.bot.set_sticker_set_thumbnail(name=pack_name, user_id=user_id, format="video", thumbnail=f)
                else:
                    raise
            os.remove(local_path)
            state.clear_awaiting(user_id)
            await update.message.reply_text("Frame updated.", reply_markup=pack_detail_keyboard(pack_name, state.is_pack_hidden(user_id, pack_name)))
        except BadRequest as e:
            await update.message.reply_text(f"Could not set frame: {e}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
        return

    if not state.check_rate_limit(user_id):
        await update.message.reply_text("Hourly limit reached. Please try again later.")
        return

    active_pack = state.get_active_pack(user_id)
    if not active_pack:
        await update.message.reply_text("Set a pack first. Use /newpack [name] or /usepack [name]")
        return

    msg = update.message
    if msg.photo:
        tg_file, kind = msg.photo[-1], "photo"
    elif msg.video:
        tg_file, kind = msg.video, "video"
    elif msg.animation:
        tg_file, kind = msg.animation, "gif"
    elif msg.document and (msg.document.mime_type or "").startswith(("image/", "video/")):
        tg_file = msg.document
        kind = "video" if "video" in msg.document.mime_type else "photo"
    else:
        await update.message.reply_text("Send a photo, GIF or video.")
        return

    file = await tg_file.get_file()
    local_path = media.tmp_path(os.path.splitext(file.file_path)[1] or ".bin")
    await file.download_to_drive(local_path)
    width, height, _ = media.probe_dimensions(local_path)
    os.remove(local_path)

    job_id = uuid.uuid4().hex
    job = {
        "kind": kind, "file_id": tg_file.file_id, "file_path": file.file_path,
        "pack": active_pack, "width": width, "height": height,
    }
    state.save_job(job_id, job)

    if not media.needs_crop(width, height):
        await build_preview(update.effective_chat.id, context, job_id, job, crop=None)
        return

    options = media.crop_options_for(width, height)
    await update.message.reply_text(
        "Image is not square. Choose area to use.",
        reply_markup=crop_choice_keyboard(job_id, options),
    )


async def handle_crop_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, job_id, choice = query.data.split(":")
    job = state.get_job(job_id)
    if not job:
        await query.edit_message_text("Request expired. Please send media again.")
        return
    if job.get("pack") and not state.is_owner_or_coowner(query.from_user.id, job["pack"]):
        await query.answer("Not your pack.", show_alert=True)
        return
    box = media.crop_box(job["width"], job["height"], choice)
    job["crop"] = list(box)
    state.save_job(job_id, job)
    await query.edit_message_text("Cropping. Please wait.")
    await build_preview(query.message.chat_id, context, job_id, job, crop=box)


async def build_preview(chat_id, context, job_id, job, crop):
    bot_file = await context.bot.get_file(job["file_id"])
    local_path = media.tmp_path(os.path.splitext(job["file_path"])[1] or ".bin")
    await bot_file.download_to_drive(local_path)

    try:
        if job["kind"] == "photo":
            out_path = media.convert_image_to_sticker(local_path, crop)
            sticker_format = "static"
        else:
            out_path = media.convert_video_to_sticker(local_path, crop)
            sticker_format = "video"
    finally:
        os.remove(local_path)

    max_bytes = MAX_STATIC_BYTES if sticker_format == "static" else MAX_VIDEO_BYTES
    if os.path.getsize(out_path) > max_bytes:
        os.remove(out_path)
        state.clear_job(job_id)
        await context.bot.send_message(chat_id, "File is too large. Try a shorter clip.")
        return

    job["out_path"] = out_path
    job["sticker_format"] = sticker_format
    state.save_job(job_id, job)

    allow_redo = media.needs_crop(job["width"], job["height"])
    with open(out_path, "rb") as f:
        await context.bot.send_sticker(
            chat_id, sticker=f, reply_markup=preview_keyboard(job_id, allow_redo)
        )


async def handle_preview_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, job_id, action = query.data.split(":")
    job = state.get_job(job_id)
    if not job:
        await query.edit_message_reply_markup(reply_markup=None)
        return
    if job.get("pack") and not state.is_owner_or_coowner(query.from_user.id, job["pack"]):
        await query.answer("Not your pack.", show_alert=True)
        return

    if action == "cancel":
        _cleanup_out_path(job)
        state.clear_job(job_id)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if action == "redo":
        _cleanup_out_path(job)
        job.pop("out_path", None)
        state.save_job(job_id, job)
        options = media.crop_options_for(job["width"], job["height"])
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            query.message.chat_id,
            "Choose area again.",
            reply_markup=crop_choice_keyboard(job_id, options),
        )
        return

    if action == "add":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            query.message.chat_id, "Choose an emoji for this sticker.", reply_markup=emoji_keyboard(job_id)
        )


async def handle_emoji_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, job_id, emoji = query.data.split(":")
    job = state.get_job(job_id)
    if not job or "out_path" not in job:
        await query.edit_message_text("Request expired. Please send media again.")
        return
    if job.get("pack") and not state.is_owner_or_coowner(query.from_user.id, job["pack"]):
        await query.answer("Not your pack.", show_alert=True)
        return

    emoji = "🙂" if emoji == "default" else emoji
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    out_path = job["out_path"]
    pack_name = job["pack"]

    try:
        with open(out_path, "rb") as f:
            sticker = InputSticker(sticker=f, format=job["sticker_format"], emoji_list=[emoji])
            try:
                await context.bot.create_new_sticker_set(
                    user_id=user_id, name=pack_name,
                    title=pack_name.split("_by_")[0].replace("_", " "),
                    stickers=[sticker],
                )
            except BadRequest as e:
                if "already" not in str(e).lower() and "exist" not in str(e).lower():
                    raise
                f.seek(0)
                await context.bot.add_sticker_to_set(user_id=user_id, name=pack_name, sticker=sticker)

        state.add_user_pack(user_id, pack_name)
        state.bump_stat("stickers_created")
        await query.edit_message_text("Sticker added.")
        await log(context.bot, f"Sticker added to {pack_name} by user {user_id}")
    except Exception as e:
        await context.bot.send_message(chat_id, "Could not create sticker. Please try again.")
        await log(context.bot, f"Sticker failed for user {user_id}: {e}")
        raise
    finally:
        _cleanup_out_path(job)
        state.clear_job(job_id)


def _cleanup_out_path(job: dict):
    path = job.get("out_path")
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------- admin ----------

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            return
        await func(update, context)
    return wrapper


@admin_only
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    state.ban_user(int(context.args[0]))
    await update.message.reply_text("Banned.")
    await log(context.bot, f"User {context.args[0]} banned by admin {update.effective_user.id}")


@admin_only
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    state.unban_user(int(context.args[0]))
    await update.message.reply_text("Unbanned.")


@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Stickers created: {state.get_stat('stickers_created')}")


@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /broadcast [text]")
        return
    text = " ".join(context.args)
    chats = state.list_chats()
    sent, failed = 0, 0
    for chat_id in chats:
        try:
            await context.bot.send_message(chat_id, text)
            sent += 1
        except (Forbidden, BadRequest):
            failed += 1
    await update.message.reply_text(f"Sent to {sent}. Failed: {failed}")


@admin_only
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import shutil
    ffmpeg_ok = os.path.exists(media.FFMPEG)
    try:
        state.redis.set("healthcheck", "1", ex=10)
        redis_ok = state.redis.get("healthcheck") == "1"
    except Exception:
        redis_ok = False
    free_gb = shutil.disk_usage("/tmp").free / (1024 ** 3)
    await update.message.reply_text(
        f"ffmpeg: {'ok' if ffmpeg_ok else 'missing'}\n"
        f"redis: {'ok' if redis_ok else 'failing'}\n"
        f"free: {free_gb:.1f} GB\n"
        f"chats: {len(state.list_chats())}\n"
        f"stickers: {state.get_stat('stickers_created')}"
    )


@admin_only
async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.get_settings()
    await update.message.reply_text(
        "Current settings:\n"
        f"start text: {s['start_text'][:60]}\n"
        f"start image: {'set' if s['start_image'] else 'none'}\n"
        f"force channel: {s['force_sub_channel'] or 'none'}\n"
        f"limit: {s['rate_limit_per_hour']}\n\n"
        "Use:\n"
        " /setstarttext [text]\n"
        " /setstartimage [reply to photo or none]\n"
        " /setforcesub [channel or off]\n"
        " /setratelimit [n]\n"
        " /resetsettings"
    )


@admin_only
async def setstarttext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /setstarttext [text]")
        return
    state.set_setting("start_text", update.message.text.split(" ", 1)[1])
    await update.message.reply_text("Start text updated.")


@admin_only
async def setstartimage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].lower() == "none":
        state.set_setting("start_image", "")
        await update.message.reply_text("Start image cleared.")
        return
    replied = update.message.reply_to_message
    if not replied or not replied.photo:
        await update.message.reply_text("Reply to a photo with /setstartimage or use /setstartimage [none]")
        return
    state.set_setting("start_image", replied.photo[-1].file_id)
    await update.message.reply_text("Start image updated.")


@admin_only
async def setforcesub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /setforcesub [channel or off]")
        return
    value = "" if context.args[0].lower() == "off" else context.args[0]
    state.set_setting("force_sub_channel", value)
    await update.message.reply_text(f"Force join {'off' if not value else value}. Updated.")


@admin_only
async def setratelimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Use: /setratelimit [n]")
        return
    state.set_setting("rate_limit_per_hour", context.args[0])
    await update.message.reply_text(f"Limit set to {context.args[0]} per hour.")


@admin_only
async def resetsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.reset_settings()
    await update.message.reply_text("Settings reset to defaults.")


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))[-1500:]
    await log(context.bot, f"Error:\n{tb}")


def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("newpack", newpack))
    app.add_handler(CommandHandler("mypacks", mypacks))
    app.add_handler(CommandHandler("usepack", usepack))
    app.add_handler(CommandHandler("renamepack", renamepack))
    app.add_handler(CommandHandler("removesticker", removesticker))

    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("setstarttext", setstarttext))
    app.add_handler(CommandHandler("setstartimage", setstartimage))
    app.add_handler(CommandHandler("setforcesub", setforcesub))
    app.add_handler(CommandHandler("setratelimit", setratelimit))
    app.add_handler(CommandHandler("resetsettings", resetsettings))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL,
        handle_media,
    ))
    app.add_handler(CallbackQueryHandler(handle_start_nav, pattern=r"^start:"))
    app.add_handler(CallbackQueryHandler(handle_pack_view, pattern=r"^pack:view:"))
    app.add_handler(CallbackQueryHandler(handle_pack_action, pattern=r"^pack:(add|rename|frame|stat|transfer|hide):"))
    app.add_handler(CallbackQueryHandler(handle_crop_choice, pattern=r"^crop:"))
    app.add_handler(CallbackQueryHandler(handle_preview_choice, pattern=r"^preview:"))
    app.add_handler(CallbackQueryHandler(handle_emoji_choice, pattern=r"^emoji:"))
    app.add_handler(CallbackQueryHandler(handle_help_nav, pattern=r"^help:"))
    app.add_handler(CallbackQueryHandler(checksub, pattern=r"^checksub$"))
