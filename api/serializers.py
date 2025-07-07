from rest_framework import serializers
from .models import TelegramUser

class TelegramUserSerializer(serializers.ModelSerializer):
    # Faqat `phone` foydalanuvchidan olinadi, qolganlari faqat chiqarish uchun
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = TelegramUser
        fields = ['id', 'telegram_id', 'phone', 'first_name', 'last_name', 'username', 'created_at']
        read_only_fields = ['telegram_id', 'first_name', 'last_name', 'username', 'created_at']