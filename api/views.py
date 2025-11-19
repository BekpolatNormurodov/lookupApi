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

# ⚠️ Session stringlarni OLDINDAN, alohida skript bilan generatsiya qilib qo'yasiz.
# Bu yerda faqat tayyor stringlardan foydalanamiz.

# with TelegramClient(StringSession(), api_id, api_hash) as client:
#     print("Yangi SESSION_STRING:")
#     print(client.session.save())

session_strings = [
    "1ApWapzMBu071X1k6zLjwlFNJy7XALpjzEyoSLZqieNcUbXyCnmtTDQ2Uj2TtfnNOpDCUQ2kzqg3_3JoUY9lHsC5gFDZM1O8a8nLaXvbAWrRehNuShMAVUwc3BKCQY5Y30CVqvqCnWxgxVFsj77ynC2g8XC54h1oBT4oEbB7CVs5KXPGJyxVtnPADZ5LMmlNBFtY2KFNyEKfvnrdOYIWHLDiIY9rNHdapphHsSP-Q7S_ON-wS2laRSOjmZZFngDKdtwY6eu0H9r8WskvddQwtIrZycfWxbiugToJy2l3j6w_Gj7IhY9NcYKRJupsk0KweRer44xEJvjEHiE8HsuNWNCzKoSXiGD0=",
    # Kerak bo'lsa yana qo'shish mumkin
]


# ===============================
# ⚙️ SOZLAMALAR
# ===============================
MIN_DELAY = 4
MAX_DELAY = 8
DELETE_EVERY_N = 300          # hozircha ishlatilmayapti, kelajak uchun
SESSION_ROTATE_EVERY = 400    # hozircha ishlatilmayapti, kelajak uchun
EMPTY_THRESHOLD = 100
LONG_BACKOFF = 15 * 60  # 15 daqiqa


# ===============================
# 🧹 YORDAMCHI FUNKSIYALAR
# ===============================
def normalize_phone(phone: str) -> str:
    """
    Telefon raqamdan barcha raqam bo'lmagan belgilarni olib tashlaydi
    va boshiga '+' qo'shib normallashtiradi.
    """
    s = re.sub(r"\D", "", str(phone))
    if not s:
        return ""
    if not s.startswith("+"):
        s = "+" + s
    return s


def generate_default_phones() -> list[str]:
    """
    Avval ulkan multiline string bo'lgan default range:
    998991240501 dan 998991241500 gacha bo'lgan raqamlar.
    """
    start = 998994411101
    end = 998994411103
    return [str(num) for num in range(start, end + 1)]


# Rangli loglar (terminal uchun)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


# ===============================
# 💾 BAZA BILAN ISHLASH (ASYNC)
# ===============================
@sync_to_async
def save_user_to_db(user, phone: str) -> bool:
    """
    TelegramUser'ni bazaga saqlash.
    Agar telegram_id + (phone, username) avvalgidek bo'lsa – qayta saqlamaydi.
    """
    exists = TelegramUser.objects.filter(telegram_id=user.id).first()

    # Mavjud bo'lsa va ma'lumotlar o'zgarmagan bo'lsa – saqlamaymiz
    if exists:
        try:
            if (
                exists.phone == phone
                and exists.username == (user.username or "")
            ):
                return False
        except Exception:
            # Agar biror narsa noto'g'ri bo'lsa – baribir yangidan yozamiz.
            pass

    TelegramUser.objects.create(
        telegram_id=user.id,
        phone=phone,  # modeldagi property orqali encrypt_data ishlaydi
        fullname=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        username=user.username or "",
    )
    return True


# ===============================
# 📡 TELETHON KLIENTINI YARATISH
# ===============================
async def make_client(idx: int) -> TelegramClient | None:
    """
    session_strings ichidan idx bo'yicha TelegramClient yaratadi.
    Agar sessiya eskirgan bo'lsa yoki avtorizatsiya yo'q bo'lsa – None qaytaradi.
    """
    session_str = session_strings[idx % len(session_strings)]
    client = TelegramClient(StringSession(session_str), api_id, api_hash)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(
                f"{RED}❌ Session {idx}: avtorizatsiya yo'q (eskirgan yoki noto‘g‘ri).{RESET}"
            )
            await client.disconnect()
            return None

        print(f"{GREEN}✅ Session {idx}: muvaffaqiyatli ulandi.{RESET}")
        return client

    except AuthKeyUnregisteredError:
        print(
            f"{RED}❌ Session {idx}: AuthKeyUnregisteredError (session eskirgan).{RESET}"
        )
        return None

    except Exception as e:
        print(f"{YELLOW}⚠️ Session {idx} bilan bog‘liq xato: {e}{RESET}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return None


# ===============================
# 🧠 TELEGRAM USERLARNI TOPISH
# ===============================
async def fetch_all_users(phones: list[str]) -> dict:
    """
    Kiritilgan telefon raqamlar bo'yicha Telegram'dagi userlarni topadi,
    bazaga saqlaydi va natijani qaytaradi.
    """
    results = []
    not_found = []
    empty_count = 0
    used = 0
    sess_idx = 0  # Hozircha bitta sessiya, keyin rotate qilish mumkin

    client = await make_client(sess_idx)
    if client is None:
        # Sessiya ishlamasa – foydali xabar qaytarib qo'yamiz
        return {
            "error": "Telegram session ishlamayapti. Iltimos, session stringni yangilang."
        }

    total = len(phones)
    print(f"\n{CYAN}🔍 {total} ta raqam tekshiruv boshlanmoqda...{RESET}")

    try:
        for i, phone in enumerate(phones, start=1):
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            await asyncio.sleep(delay)
            print(f"{CYAN}⏳ {i}/{total} → {phone}{RESET}")

            try:
                contact = InputPhoneContact(
                    client_id=i,
                    phone=phone,
                    first_name="",
                    last_name="",
                )

                res = await client(ImportContactsRequest([contact]))
                user = res.users[0] if res.users else None

                if user:
                    await save_user_to_db(user, phone)
                    results.append({"phone": phone, "found": True})

                    print(
                        f"{GREEN}✅ {phone} "
                        f"({user.first_name or ''} @{user.username or ''}){RESET}, "
                        f"{GREEN}{len(results)}{CYAN}/{RED}{len(not_found)}{RESET}"
                    )

                    empty_count = 0

                    # Kontaktlarni tozalab turamiz
                    await client(DeleteContactsRequest(id=[user]))

                else:
                    not_found.append(phone)
                    empty_count += 1
                    print(
                        f"{RED}❌ {phone} topilmadi{RESET}, "
                        f"{GREEN}{len(results)}{CYAN}/{RED}{len(not_found)}{RESET}"
                    )

            except FloodWaitError as e:
                wait = e.seconds + random.randint(3, 8)
                print(f"{YELLOW}⏸ FloodWaitError: {wait}s kutish...{RESET}")
                await asyncio.sleep(wait)
                continue

            except Exception as e:
                print(f"{YELLOW}⚠️ {phone} uchun xato: {e}{RESET}")
                continue

            used += 1

            # Ketma-ket juda ko'p "not found" bo'lsa – uzoq pauza
            if empty_count >= EMPTY_THRESHOLD:
                print(
                    f"{YELLOW}⚠️ {empty_count} ta ketma-ket topilmadi. "
                    f"{LONG_BACKOFF // 60} daqiqa kutish...{RESET}"
                )
                await asyncio.sleep(LONG_BACKOFF)
                empty_count = 0

        print(f"\n{GREEN}✅ {total} ta raqam tekshirildi!{RESET}\n")

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    return {
        "found": results,
        "not_found": not_found,
        "total": total,
    }


# ===============================
# 📦 TELEGRAM USER VIEWSET
# ===============================
class TelegramUserViewSet(ModelViewSet):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer

    def create(self, request, *args, **kwargs):
        """
        POST /telegram-users/
        Body:
        {
            "phones": [
                "99899123....",
                "99897....",
                ...
            ]
        }

        Agar phones berilmasa – default range (998991240501–998991241500) ishlatiladi.
        """
        raw_phones = request.data.get("phones")

        # phones string bo'lsa (multi-line)
        if isinstance(raw_phones, str):
            phones = [
                p.strip() for p in raw_phones.splitlines() if p.strip()
            ]
        # phones list bo'lsa
        elif isinstance(raw_phones, list):
            phones = [str(p).strip() for p in raw_phones if str(p).strip()]
        # umuman kelmagan bo'lsa – default range
        else:
            phones = generate_default_phones()

        # Normalizatsiya
        phones = [normalize_phone(p) for p in phones if p]

        if not phones:
            return Response(
                {"error": "Telefon raqamlar topilmadi."},
                status=400,
            )

        # Asinxron funksiya natijasini sync kontekstda olish
        all_results = async_to_sync(fetch_all_users)(phones)

        if "error" in all_results:
            return Response(all_results, status=500)

        return Response(all_results, status=200)


# ===============================
# 🔍 QIDIRISH
# ===============================
@api_view(["GET"])
def search_telegram_user(request):
    """
    GET /search_telegram_user/?id=123456
    telegram_id bo'yicha qidiradi.
    """
    query = request.GET.get("id")
    if not query:
        return Response(
            {"error": "Query param id is required"},
            status=400,
        )

    # Agar telegram_id IntegerField bo'lsa, icontains emas, exact ishlatish yaxshi.
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
            return Response({"error": "Hali hech qanday foydalanuvchi yo'q."}, status=404)

        serializer = TelegramUserSerializer(latest_data)
        return Response(serializer.data)
