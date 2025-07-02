from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from asgiref.sync import sync_to_async, async_to_sync
from api.models import TelegramUser
from api.serializers import TelegramUserSerializer

api_id = 20470849
api_hash = 'b33c924cdd01330cfac1ea4ff5b5b89d'

class TelegramUserViewSet(ModelViewSet):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer

    def create(self, request, *args, **kwargs):
        start = 998946792227
        end = 998946792229
        phones_list = [str(p) for p in range(start, end)]
        results = []

        @sync_to_async
        def save_user_to_db(user, phone):
            obj, created = TelegramUser.objects.update_or_create(
                telegram_id=user.id,
                defaults={
                    'phone': phone,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'username': user.username
                }
            )
            return {
                'telegram_id': user.id,
                'phone': phone,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'saved': created
            }

        async def fetch_all_users():
            async with TelegramClient('session', api_id, api_hash) as client:
                for phone in phones_list:
                    contact = InputPhoneContact(client_id=0, phone=phone, first_name="Null", last_name="User")
                    result = await client(ImportContactsRequest([contact]))
                    user = result.users[0] if result.users else None
                    if user:
                        await client(DeleteContactsRequest(id=[user]))
                        user_data = await save_user_to_db(user, phone)
                        results.append(user_data)
                    else:
                        results.append({'phone': phone, 'error': 'Foydalanuvchi topilmadi'})
            return results

        # Barcha foydalanuvchilarni sinxron ishlovchi funksiya orqali olamiz
        all_results = async_to_sync(fetch_all_users)()
        return Response(all_results)
