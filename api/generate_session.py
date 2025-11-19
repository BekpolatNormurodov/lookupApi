from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 23896913
api_hash = "fea158b1a7e6a89cc84ef61b53b465cb"

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("Yangi SESSION_STRING:")
    print(client.session.save())
