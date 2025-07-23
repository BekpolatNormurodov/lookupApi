import asyncio
import random
from asgiref.sync import sync_to_async, async_to_sync
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import api_view
from api.models import TelegramUser
from api.utils import fernet
from api.serializers import TelegramUserSerializer

# Telegram API credentials
api_id = 20727573
api_hash = '4d677f4474803f0e54c378ff138aa3d8'

class TelegramUserViewSet(ModelViewSet):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer

    def create(self, request, *args, **kwargs):
        phones_list = request.data.get("phones", [])

        if not phones_list or not isinstance(phones_list, list):
            return Response({'error': 'Telefon raqamlar listda bo‘lishi kerak'}, status=400)

        @sync_to_async
        def save_user_to_db(user, phone):
            encrypted_phone = fernet.encrypt(phone.encode())

            # Eski yozuvlar ichidan mos keladiganlarini tekshiramiz
            all_users = TelegramUser.objects.all()

            for existing in all_users:
                try:
                    existing_phone = fernet.decrypt(existing.phone).decode()
                except:
                    continue

                if existing.telegram_id == user.id and existing_phone == phone:
                    if (
                        existing.first_name == (user.first_name or '') and
                        existing.last_name == (user.last_name or '') and
                        existing.username == (user.username or '')
                    ):
                        # Ma'lumotlar o‘zgarmagan, saqlamaymiz
                        return {
                            'telegram_id': user.id,
                            'phone': phone,
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                            'username': user.username,
                            'saved': False,
                            'message': '❌ O‘xshash maʼlumot bor, saqlanmadi'
                        }

            # Maʼlumotlar o‘zgargan, yangi yozuv sifatida saqlaymiz
            new_user = TelegramUser.objects.create(
                telegram_id=user.id,
                phone=encrypted_phone,
                first_name=user.first_name or '',
                last_name=user.last_name or '',
                username=user.username or ''
            )
            return {
                'telegram_id': new_user.telegram_id,
                'phone': phone,
                'first_name': new_user.first_name,
                'last_name': new_user.last_name,
                'username': new_user.username,
                'saved': True,
                'message': '✅ Yangi yozuv saqlandi'
            }

        async def fetch_all_users():
            results = []
            async with TelegramClient('session', api_id, api_hash) as client:
                for phone in phones_list:
                    await asyncio.sleep(random.uniform(3, 5))
                    contact = InputPhoneContact(client_id=0, phone=phone, first_name="", last_name="")
                    try:
                        result = await client(ImportContactsRequest([contact]))
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                        continue

                    user = result.users[0] if result.users else None
                    if user:
                        await client(DeleteContactsRequest(id=[user]))
                        user_data = await save_user_to_db(user, phone)
                        results.append(user_data)
                    else:
                        results.append({'phone': phone, 'error': 'Telegram foydalanuvchisi topilmadi'})
            return results

        all_results = async_to_sync(fetch_all_users)()
        return Response(all_results)

@api_view(['GET'])
def search_telegram_user(request):
    query = request.GET.get('id')
    if not query:
        return Response({'error': 'Query param id is required'}, status=400)

    users = TelegramUser.objects.filter(telegram_id__icontains=query)
    results = TelegramUserSerializer(users, many=True).data
    return Response(results)
