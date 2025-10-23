import asyncio
import random
import re
from asgiref.sync import sync_to_async
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact

from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.views import APIView

from api.models import TelegramUser
from api.utils import fernet
from api.serializers import TelegramUserSerializer


# ===============================
# ⚙️ TELEGRAM API MA'LUMOTLARI
# ===============================
api_id = 21065434
api_hash = '458a0afe56e31b8a825ae8cd07fe80d5'

# 💾 Bir yoki bir nechta session stringlar (navbat bilan ishlaydi)
# with TelegramClient(StringSession(), api_id, api_hash) as client:
#      print(client.session.save())
session_strings = [
    "1ApWapzMBu3-X_UBG4g7dpWujuoa2uz5q8hfCX8iJIORyLyvZkw8cEgc4ZKBz5Uqv1ffBJbxgfKbLL_3DwsVZ1esb6rpg2fPrhBpmGP1sKUYNzAFCVIQbR-ObeK8KzlOrBGVmtPy_5GKKDhQzvOriW5Zzlwo8-QvgmFr-JGbuES1f9CvX9mSNymP4JTiXC00C-MjpY1tKr4CDI2zYjP7hNaT5ptXCDBMHt-gbf0hnC08EGDjbTP1_Vfd98wyvcnmlKG_G7p7l3pIuW1NVkZ7-3zSl54m5eHZKMKpm142oYBAeuDnEz0q6OqqW7rE1-NJvRj2PLxVHxlB5U65HjdlSyWzUTTIrJOo=",
    # "YOUR_SESSION_STRING_2_HERE",  # agar ikkinchi akkaunt qo‘shmoqchi bo‘lsangiz
]


# ===============================
# ⏳ Sozlamalar (tavsiya qilingan)
# ===============================
MIN_DELAY = 4          # har raqam orasida kamida 4s
MAX_DELAY = 8          # maksimal 8s kutish
DELETE_EVERY_N = 300   # har 300 raqamdan keyin kontaktlarni tozalash
SESSION_ROTATE_EVERY = 400  # har 400 so‘rovdan keyin sessiya almashtirish (agar bir nechta bo‘lsa)
EMPTY_THRESHOLD = 5    # ketma-ket 5 marta topilmasa 15 daqiqa kutadi
LONG_BACKOFF = 15 * 60  # 15 daqiqa soft-ban kutish


# Telefon raqamni formatlash
def normalize_phone(phone: str) -> str:
    s = re.sub(r"\D", "", phone)
    if not s:
        return ""
    if not s.startswith("+"):
        s = "+" + s
    return s


# Rangli log chiqarish (terminal uchun)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


class TelegramUserViewSet(ModelViewSet):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer

    def create(self, request, *args, **kwargs):
        # Default raqamlar (sinov uchun)
        phones = """
998938052221
998938052222
998938052223
998938052224
998938052225
998938052226
998938052227
998938052228
998938052229
998938052230
"""  # test ma'lumot

        phones_list = request.data.get("phones", phones)
        if isinstance(phones_list, str):
            phones_list = [p.strip() for p in phones_list.splitlines() if p.strip()]
        phones_list = [normalize_phone(p) for p in phones_list if p.strip()]

        if not phones_list:
            return Response({"error": "Telefon raqamlar topilmadi."}, status=400)

        # 🔒 Bazaga saqlash (async)
        @sync_to_async
        def save_user_to_db(user, phone):
            encrypted_phone = fernet.encrypt(phone.encode())
            exists = TelegramUser.objects.filter(telegram_id=user.id).first()

            if exists:
                try:
                    existing_phone = fernet.decrypt(exists.phone).decode()
                    if (
                        existing_phone == phone
                        and exists.first_name == (user.first_name or "")
                        and exists.last_name == (user.last_name or "")
                        and exists.username == (user.username or "")
                    ):
                        return False
                except Exception:
                    pass

            TelegramUser.objects.create(
                telegram_id=user.id,
                phone=encrypted_phone,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                username=user.username or "",
            )
            return True

        # 🧠 Asosiy asinxron funksiya
        async def fetch_all_users(phones):
            results = []
            not_found = []
            empty_count = 0
            used = 0
            sess_idx = 0

            # Sessiya yaratish funksiyasi
            async def make_client(idx):
                session = session_strings[idx % len(session_strings)]
                client = TelegramClient(StringSession(session), api_id, api_hash)
                await client.connect()
                if not await client.is_user_authorized():
                    raise RuntimeError(f"Session {idx} eskirgan yoki noto‘g‘ri.")
                return client

            client = await make_client(sess_idx)
            total = len(phones)
            print(f"\n{CYAN}🔍 {total} ta raqam tekshiruv boshlanmoqda...{RESET}")

            try:
                for i, phone in enumerate(phones, start=1):
                    delay = random.uniform(MIN_DELAY, MAX_DELAY)
                    await asyncio.sleep(delay)
                    print(f"{CYAN}⏳ {i}/{total} → {phone} (kutish {delay:.1f}s){RESET}")

                    # Sessiyani almashtirish (agar kerak bo‘lsa)
                    if len(session_strings) > 1 and used >= SESSION_ROTATE_EVERY:
                        try:
                            await client.disconnect()
                        except:
                            pass
                        sess_idx = (sess_idx + 1) % len(session_strings)
                        client = await make_client(sess_idx)
                        used = 0
                        print(f"{YELLOW}🔁 Sessiya almashtirildi → index {sess_idx}{RESET}")

                    try:
                        contact = InputPhoneContact(client_id=i, phone=phone, first_name="", last_name="")
                        res = await client(ImportContactsRequest([contact]))
                        user = res.users[0] if res.users else None

                        if user:
                            await save_user_to_db(user, phone)
                            print(f"{GREEN}✅ {phone} — Topildi ({user.first_name or ''} @{user.username or ''}){RESET}, {GREEN}{len(results)+1}{CYAN}/{RED}{len(not_found)}")
                            results.append({"phone": phone, "found": True})
                            empty_count = 0
                            await client(DeleteContactsRequest(id=[user]))
                        else:
                            print(f"{RED}❌ {phone} — Topilmadi{RESET}, {GREEN}{len(results)}/{RED}{len(not_found)+1}")
                            not_found.append(phone)
                            empty_count += 1

                    except FloodWaitError as e:
                        wait = e.seconds + random.randint(3, 8)
                        print(f"{YELLOW}⏸ FloodWaitError: {e.seconds}s → {wait}s kutish{RESET}")
                        await asyncio.sleep(wait)
                        continue
                    except (ConnectionError, OSError) as ce:
                        print(f"{YELLOW}⚠️ Tarmoq xatosi: {ce}. 20sdan so‘ng qayta ulanadi...{RESET}")
                        try:
                            await client.disconnect()
                        except:
                            pass
                        await asyncio.sleep(20)
                        client = await make_client(sess_idx)
                        continue
                    except Exception as e:
                        print(f"{YELLOW}⚠️ {phone} uchun xato: {e}{RESET}")
                        continue

                    used += 1

                    # Har DELETE_EVERY_N tadan keyin kontaktlarni tozalash
                    if used % DELETE_EVERY_N == 0:
                        try:
                            print(f"{CYAN}🧹 Kontaktlarni tozalash...{RESET}")
                            await asyncio.sleep(random.uniform(2, 5))
                            await client(DeleteContactsRequest([]))
                        except Exception:
                            pass

                    # Soft-ban ehtimoli
                    if empty_count >= EMPTY_THRESHOLD:
                        print(f"{YELLOW}⚠️ {empty_count} ta ketma-ket topilmadi. {LONG_BACKOFF//60} daqiqa kutish...{RESET}")
                        await asyncio.sleep(LONG_BACKOFF)
                        empty_count = 0

                print(f"\n{GREEN}✅ Barcha {total} ta raqam tekshirildi!{RESET}\n")

            finally:
                await client.disconnect()

            return {"found": results, "not_found": not_found, "total": total}

        # Ishni bajarish
        all_results = asyncio.run(fetch_all_users(phones_list))
        return Response(all_results)


# 🔍 Qidirish endpoint
@api_view(["GET"])
def search_telegram_user(request):
    query = request.GET.get("id")
    if not query:
        return Response({"error": "Query param id is required"}, status=400)

    users = TelegramUser.objects.filter(telegram_id__icontains=query)
    results = TelegramUserSerializer(users, many=True).data
    return Response(results)


# 🕒 Oxirgi foydalanuvchini olish
class LatestUserDataView(APIView):
    def get(self, request):
        latest_data = TelegramUser.objects.latest("created_at")
        serializer = TelegramUserSerializer(latest_data)
        return Response(serializer.data)
