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
        phones = [
            "998946792220",
            "998938052295",
            "998994411102"
        ]

        @sync_to_async
        def save_user_to_db(user, phone):
            return TelegramUser.objects.update_or_create(
                telegram_id=user.id,
                defaults={
                    'phone': phone,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'username': user.username
                }
            )

        async def fetch_users(phone_list):
            results = []
            async with TelegramClient('session', api_id, api_hash) as client:
                for phone in phone_list:
                    contact = InputPhoneContact(client_id=0, phone=phone, first_name="Null", last_name="User")
                    result = await client(ImportContactsRequest([contact]))
                    user = result.users[0] if result.users else None

                    if user:
                        await client(DeleteContactsRequest(id=[user]))
                        obj, created = await save_user_to_db(user, phone)
                        user_data = {
                            'telegram_id': user.id,
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                            'username': user.username,
                            'saved': created
                        }
                        print(f"✅ {phone} -> {user_data}")  # Terminalga chiqarish
                        results.append(user_data)
                    else:
                        print(f"❌ {phone} -> Foydalanuvchi topilmadi")
                        results.append({'phone': phone, 'error': 'Foydalanuvchi topilmadi'})
            return results

        result = async_to_sync(fetch_users)(phones)
        return Response(result)
