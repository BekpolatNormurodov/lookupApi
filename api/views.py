import asyncio
import random
from asgiref.sync import async_to_sync, sync_to_async
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from telethon.sessions import MemorySession

from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.views import APIView

from api.models import TelegramUser
from api.utils import fernet
from api.serializers import TelegramUserSerializer

# Telegram API ma'lumotlari
api_id = 26106729
api_hash = 'bb13221ab81b637a7a8a23caec2af078'


class TelegramUserViewSet(ModelViewSet):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer

    def create(self, request, *args, **kwargs):
        phones = "998889773960 998889773961 998889773962 998889773963 998889773964 998889773965 998889773966 998889773967 998889773968 998889773969 998889773970 998889773971 998889773972 998889773973 998889773974 998889773975 998889773976 998889773977 998889773978 998889773979 998889773980 998889773981 998889773982 998889773983 998889773984 998889773985 998889773986 998889773987 998889773988 998889773989 998889773990"
        phones_format = [p.strip() for p in phones.split() if p.strip()]
        phones_list = request.data.get("phones", phones_format)
        if not phones_list or not isinstance(phones_list, list):
            return Response({'error': 'Telefon raqamlar listda bo‘lishi kerak'}, status=400)

        @sync_to_async
        def save_user_to_db(user, phone):
            encrypted_phone = fernet.encrypt(phone.encode())

            all_users = TelegramUser.objects.all()
            for existing in all_users:
                try:
                    existing_phone = fernet.decrypt(existing.phone).decode()
                except Exception:
                    continue

                if existing.telegram_id == user.id and existing_phone == phone:
                    if (
                        existing.first_name == (user.first_name or '') and
                        existing.last_name == (user.last_name or '') and
                        existing.username == (user.username or '')
                    ):
                        return {
                            'telegram_id': user.id,
                            'phone': phone,
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                            'username': user.username,
                            'saved': False,
                            'message': '❌ O‘xshash maʼlumot bor, saqlanmadi'
                        }

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
            async with TelegramClient(MemorySession(), api_id, api_hash) as client:
                await client.start()
                for phone in phones_list:
                    await asyncio.sleep(1)
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
                        results.append({
                            'phone': phone,
                            'error': 'Telegram foydalanuvchisi topilmadi'
                        })
            return results

        # MUHIM: asyncio.run bilan coroutine’ni sinxron ishlatamiz
        all_results = asyncio.run(fetch_all_users())
        return Response(all_results)


@api_view(['GET'])
def search_telegram_user(request):
    query = request.GET.get('id')
    if not query:
        return Response({'error': 'Query param id is required'}, status=400)

    users = TelegramUser.objects.filter(telegram_id__icontains=query)
    results = TelegramUserSerializer(users, many=True).data
    return Response(results)


class LatestUserDataView(APIView):
    def get(self, request):
        latest_data = TelegramUser.objects.latest('created_at')
        serializer = TelegramUserSerializer(latest_data)
        return Response(serializer.data)
