from cryptography.fernet import Fernet
from django.conf import settings

fernet = Fernet(settings.FERNET_KEY.encode())

def encrypt_data(value):
    if isinstance(value, str):
        value = value.encode()
    encrypted = fernet.encrypt(value)
    return encrypted.decode()

def decrypt_data(value):
    if isinstance(value, str):
        value = value.encode()
    decrypted = fernet.decrypt(value)
    return decrypted.decode()
