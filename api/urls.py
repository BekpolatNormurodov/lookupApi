from rest_framework import routers
from api.views import TelegramUserViewSet

urlpatterns = []
router = routers.SimpleRouter()
router.register('', TelegramUserViewSet, basename='telegramuser')

urlpatterns += router.urls