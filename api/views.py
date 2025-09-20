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
        phones = """998938052200    
998938052201    
998938052202    
998938052203    
998938052204    
998938052205    
998938052206    
998938052207    
998938052208    
998938052209    
998938052210    
998938052211    
998938052212    
998938052213    
998938052214    
998938052215    
998938052216    
998938052217    
998938052218    
998938052219    
998938052220    
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
998938052231    
998938052232    
998938052233    
998938052234    
998938052235    
998938052236    
998938052237    
998938052238    
998938052239    
998938052240    
998938052241    
998938052242    
998938052243    
998938052244    
998938052245    
998938052246    
998938052247    
998938052248    
998938052249    
998938052250    
998938052251    
998938052252    
998938052253    
998938052254    
998938052255    
998938052256    
998938052257    
998938052258    
998938052259    
998938052260    
998938052261    
998938052262    
998938052263    
998938052264    
998938052265    
998938052266    
998938052267    
998938052268    
998938052269    
998938052270    
998938052271    
998938052272    
998938052273    
998938052274    
998938052275    
998938052276    
998938052277    
998938052278    
998938052279    
998938052280    
998938052281    
998938052282    
998938052283    
998938052284    
998938052285    
998938052286    
998938052287    
998938052288    
998938052289    
998938052290    
998938052291    
998938052292    
998938052293    
998938052294    
998938052295    
998938052296    
998938052297    
998938052298    
998938052299    
"""
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
                    await asyncio.sleep(random.uniform(3, 7))
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
