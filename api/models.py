from django.db import models
from .utils import encrypt_data, decrypt_data

class TelegramUser(models.Model):
    _phone = models.TextField(db_column='phone')  # Shifrlanadigan maydon
    telegram_id = models.BigIntegerField()
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def phone(self):
        try:
            return decrypt_data(self._phone)
        except Exception:
            return "[Xatolik]"

    @phone.setter
    def phone(self, value):
        self._phone = encrypt_data(value)

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} ({self.phone})"

