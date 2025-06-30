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
        phones = "998938052295"
        if not phones:
            return Response({'error': 'Telefon raqam kerak'}, status=400)

        # ORM chaqiruvini asinxronlashtiramiz
        @sync_to_async
        def save_user_to_db(user, phones):
            return TelegramUser.objects.update_or_create(
                telegram_id=user.id,
                defaults={
                    'phone': phones,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'username': user.username
                }
            )
        
        # Telegram orqali foydalanuvchini olish
        async def fetch_user(phones):
            async with TelegramClient('session', api_id, api_hash) as client:
                contact = InputPhoneContact(client_id=0, phone=phones, first_name="Temp", last_name="User")
                result = await client(ImportContactsRequest([contact]))
                user = result.users[0] if result.users else None

                if user:
                    await client(DeleteContactsRequest(id=[user]))
                    obj, created = await save_user_to_db(user, phones)
                    return {
                        'telegram_id': user.id,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'username': user.username,
                        'saved': created
                    }
                else:
                    return {'error': 'Foydalanuvchi topilmadi'}

        # Asinxron funksiyani sinxron chaqiramiz
        result = async_to_sync(fetch_user)(phones)
        return Response(result)
