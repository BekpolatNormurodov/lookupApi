import asyncio
import random
import re

from asgiref.sync import sync_to_async, async_to_sync
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, AuthKeyUnregisteredError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact

from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.views import APIView

from api.models import TelegramUser

from api.serializers import TelegramUserSerializer


# ===============================
# ⚙️ TELEGRAM API MA'LUMOTLARI
# ===============================
api_id = 28404288
api_hash = "d560c74564f1be204bdbf892b7c392bc"

# Telegram sessiyalar (oldindan generatsiya qilingan)
session_strings = [
    "1ApWapzMBu071X1k6zLjwlFNJy7XALpjzEyoSLZqieNcUbXyCnmtTDQ2Uj2TtfnNOpDCUQ2kzqg3_3JoUY9lHsC5gFDZM1O8a8nLaXvbAWrRehNuShMAVUwc3BKCQY5Y30CVqvqCnWxgxVFsj77ynC2g8XC54h1oBT4oEbB7CVs5KXPGJyxVtnPADZ5LMmlNBFtY2KFNyEKfvnrdOYIWHLDiIY9rNHdapphHsSP-Q7S_ON-wS2laRSOjmZZFngDKdtwY6eu0H9r8WskvddQwtIrZycfWxbiugToJy2l3j6w_Gj7IhY9NcYKRJupsk0KweRer44xEJvjEHiE8HsuNWNCzKoSXiGD0=",
]


# ===============================
# 🌐 PROKSI SOZLAMLARI
# ===============================
USE_PROXY = True

# Har bir sessiya uchun alohida proksi berish (har xil IP)
PROXIES = [
    ('socks5', '123.123.123.123', 1080, True, 'proxy_user1', 'proxy_pass1'),
    ('socks5', '222.222.222.222', 1080, True, 'proxy_user2', 'proxy_pass2'),
    ('socks5', '333.333.333.333', 1080, True, 'proxy_user3', 'proxy_pass3'),
]


# ===============================
# ⚙️ SOZLAMALAR
# ===============================
MIN_DELAY = 4
MAX_DELAY = 8
EMPTY_THRESHOLD = 100
LONG_BACKOFF = 15 * 60  # 15 daqiqa


# ===============================
# 🧹 YORDAMCHI FUNKSIYALAR
# ===============================
def normalize_phone(phone: str) -> str:
    s = re.sub(r"\D", "", str(phone))
    if not s:
        return ""
    if not s.startswith("+"):
        s = "+" + s
    return s


def generate_default_phones() -> list[str]:
    start = 998938052290
    end = 998994411103
    return [str(num) for num in range(start, end + 1)]


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


# ===============================
# 💾 BAZA BILAN ISHLASH
# ===============================
@sync_to_async
def save_user_to_db(user, phone: str) -> bool:
    exists = TelegramUser.objects.filter(telegram_id=user.id).first()
    if exists:
        if (
            exists.phone == phone
            and exists.username == (user.username or "")
        ):
            return False
    TelegramUser.objects.create(
        telegram_id=user.id,
        phone=phone,
        fullname=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        username=user.username or "",
    )
    return True


# ===============================
# 📡 TELETHON KLIENTI (PROKSI BILAN)
# ===============================
async def make_client(idx: int) -> TelegramClient | None:
    session_str = session_strings[idx % len(session_strings)]

    extra_kwargs = {}
    if USE_PROXY and idx < len(PROXIES):
        extra_kwargs["proxy"] = PROXIES[idx]
        print(f"{CYAN}🌐 Session {idx} proksi bilan ulanmoqda: {PROXIES[idx][1]}{RESET}")

    client = TelegramClient(
        StringSession(session_str),
        api_id,
        api_hash,
        **extra_kwargs
    )

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(f"{RED}❌ Session {idx}: avtorizatsiya yo'q.{RESET}")
            await client.disconnect()
            return None

        print(f"{GREEN}✅ Session {idx}: muvaffaqiyatli ulandi.{RESET}")
        return client

    except AuthKeyUnregisteredError:
        print(f"{RED}❌ Session {idx}: eskirgan (AuthKeyUnregisteredError).{RESET}")
        return None
    except Exception as e:
        print(f"{YELLOW}⚠️ Session {idx} xato: {e}{RESET}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return None


# ===============================
# 🧠 TELEGRAM USERLARNI TOPISH
# ===============================
async def fetch_all_users(phones: list[str]) -> dict:
    results = []
    not_found = []
    empty_count = 0
    sess_idx = 0

    client = await make_client(sess_idx)
    if client is None:
        return {"error": "Telegram session ishlamayapti. Session stringni yangilang."}

    total = len(phones)
    print(f"\n{CYAN}🔍 {total} ta raqam tekshiruv boshlanmoqda...{RESET}")

    try:
        for i, phone in enumerate(phones, start=1):
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            await asyncio.sleep(delay)
            print(f"{CYAN}⏳ {i}/{total} → {phone}{RESET}")

            try:
                contact = InputPhoneContact(client_id=i, phone=phone, first_name="", last_name="")
                res = await client(ImportContactsRequest([contact]))
                user = res.users[0] if res.users else None

                if user:
                    await save_user_to_db(user, phone)
                    results.append({"phone": phone, "found": True})
                    print(f"{GREEN}✅ {phone} ({user.first_name or ''} @{user.username or ''}){RESET}")
                    empty_count = 0
                    await client(DeleteContactsRequest(id=[user]))
                else:
                    not_found.append(phone)
                    empty_count += 1
                    print(f"{RED}❌ {phone} topilmadi{RESET}")

            except FloodWaitError as e:
                wait = e.seconds + random.randint(3, 8)
                print(f"{YELLOW}⏸ FloodWaitError: {wait}s kutish...{RESET}")
                await asyncio.sleep(wait)
                continue

            except Exception as e:
                print(f"{YELLOW}⚠️ {phone} uchun xato: {e}{RESET}")
                continue

            if empty_count >= EMPTY_THRESHOLD:
                print(f"{YELLOW}⚠️ {empty_count} ketma-ket topilmadi. {LONG_BACKOFF//60} daqiqa kutish...{RESET}")
                await asyncio.sleep(LONG_BACKOFF)
                empty_count = 0

        print(f"\n{GREEN}✅ {total} ta raqam tekshirildi!{RESET}\n")

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    return {"found": results, "not_found": not_found, "total": total}


# ===============================
# 📦 TELEGRAM USER VIEWSET
# ===============================
class TelegramUserViewSet(ModelViewSet):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer

    def create(self, request, *args, **kwargs):
        raw_phones = request.data.get("phones")

        if isinstance(raw_phones, str):
            phones = [p.strip() for p in raw_phones.splitlines() if p.strip()]
        elif isinstance(raw_phones, list):
            phones = [str(p).strip() for p in raw_phones if str(p).strip()]
        else:
            phones = generate_default_phones()

        phones = [normalize_phone(p) for p in phones if p]

        if not phones:
            return Response({"error": "Telefon raqamlar topilmadi."}, status=400)

        all_results = async_to_sync(fetch_all_users)(phones)
        if "error" in all_results:
            return Response(all_results, status=500)
        return Response(all_results, status=200)


# ===============================
# 🔍 QIDIRISH
# ===============================
@api_view(["GET"])
def search_telegram_user(request):
    query = request.GET.get("id")
    if not query:
        return Response({"error": "Query param id is required"}, status=400)

    users = TelegramUser.objects.filter(telegram_id=query)
    results = TelegramUserSerializer(users, many=True).data
    return Response(results)


# ===============================
# 🕒 ENG OXIRGI USER
# ===============================
class LatestUserDataView(APIView):
    def get(self, request):
        try:
            latest_data = TelegramUser.objects.latest("created_at")
        except TelegramUser.DoesNotExist:
            return Response({"error": "Hali foydalanuvchi yo‘q."}, status=404)

        serializer = TelegramUserSerializer(latest_data)
        return Response(serializer.data)
