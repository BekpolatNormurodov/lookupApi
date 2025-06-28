from rest_framework import serializers
from .models import TelegramUser

class TelegramUserSerializer(serializers.ModelSerializer):
    # Faqat `phone` foydalanuvchidan olinadi, qolganlari faqat chiqarish uchun
    class Meta:
        model = TelegramUser
        fields = ['telegram_id', 'phone', 'first_name', 'last_name', 'username']
        read_only_fields = ['telegram_id', 'first_name', 'last_name', 'username']