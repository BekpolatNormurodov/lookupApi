import asyncio
from asgiref.sync import sync_to_async, async_to_sync
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import traceback
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import api_view
from api.models import TelegramUser
from api.serializers import TelegramUserSerializer

# 🔐 Telegram API credentials (bot yaratganingizdagi ma'lumot)
api_id = 20727573
api_hash = '4d677f4474803f0e54c378ff138aa3d8'

class TelegramUserViewSet(ModelViewSet):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer

    def create(self, request, *args, **kwargs):
        # 📞 Tekshiriladigan telefon raqamlar oralig'i
        start = 998991240505
        end = 998991240507
        phones_list = [str(p) for p in range(start, end)]

        @sync_to_async
        def save_user_to_db(user, phone):
            """
            Foydalanuvchini faqat ma'lumotlar o'zgargan bo'lsa yangilaydi yoki yaratadi.
            """
            existing = TelegramUser.objects.filter(telegram_id=user.id).first()

            if existing:
                changed = False
                if existing.first_name != user.first_name:
                    existing.first_name = user.first_name
                    changed = True
                if existing.last_name != user.last_name:
                    existing.last_name = user.last_name
                    changed = True
                if existing.username != user.username:
                    existing.username = user.username
                    changed = True
                if existing.phone != phone:
                    existing.phone = phone
                    changed = True

                if changed:
                    existing.save()
                    print("✏️ Ma'lumotlar yangilandi.")
                    return {
                        'telegram_id': user.id,
                        'phone': phone,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'username': user.username,
                        'saved': True
                    }
                else:
                    print("- O'zgarish yo'q, saqlanmadi.")
                    return {
                        'telegram_id': user.id,
                        'phone': phone,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'username': user.username,
                        'saved': False
                    }
            else:
                TelegramUser.objects.create(
                    telegram_id=user.id,
                    phone=phone,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username
                )
                print("🆕 Foydalanuvchi yaratildi.")
                return {
                    'telegram_id': user.id,
                    'phone': phone,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'username': user.username,
                    'saved': True
                }

        async def fetch_all_users():
            """
            Telegram kontaktlar orqali foydalanuvchilarni aniqlaydi
            va ularni bazaga saqlaydi.
            """
            results = []

            async with TelegramClient('session', api_id, api_hash) as client:
                for phone in phones_list:
                    print(f"📞 Tekshirilmoqda: {phone}")

                    await asyncio.sleep(5)  # Flood limitdan saqlanish

                    contact = InputPhoneContact(
                        client_id=0,
                        phone=phone,
                        first_name="",
                        last_name=""
                    )
                    try:
                        result = await client(ImportContactsRequest([contact]))
                    except FloodWaitError as e:
                        print(f"⏳ FloodWaitError: {e.seconds} soniya kutish...")
                        await asyncio.sleep(e.seconds)
                        continue
                    except Exception as e:
                        print(f"⚠️ Xatolik: {e}")
                        traceback.print_exc()  # To'liq traceback chiqarish
                        results.append({'phone': phone, 'error': str(e)})
                        continue

                    user = result.users[0] if result.users else None

                    if user:
                        try:
                            await client(DeleteContactsRequest(id=[user]))
                        except Exception as e:
                            print(f"⚠️ Kontakt o'chirishda xatolik: {e}")

                        user_data = await save_user_to_db(user, phone)
                        print(f"✅ Topildi: {user.first_name} @{user.username or ''}")
                        results.append(user_data)
                    else:
                        print(f"❌ Topilmadi: {phone}")
                        results.append({'phone': phone, 'error': 'Foydalanuvchi topilmadi'})

            return results
        # 🔁 Async funksiyani sinxron bajarish
        all_results = async_to_sync(fetch_all_users)()
        return Response(all_results)


@api_view(['GET'])
def search_telegram_user(request):
    """
    Telegram foydalanuvchilarni `phone`, `telegram_id` orqali izlash.
    URL: /search/?q=9989xxxxx
    """
    query = request.GET.get('q')
    if not query:
        return Response({'error': 'Query param `q` is required'}, status=400)

    if query.isdigit():
        users = TelegramUser.objects.filter(
            phone__icontains=query
        ) | TelegramUser.objects.filter(
            telegram_id__icontains=query
        )
    else:
        users = TelegramUser.objects.none()

    serializer = TelegramUserSerializer(users, many=True)
    return Response(serializer.data)