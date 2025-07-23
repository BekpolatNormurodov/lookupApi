from rest_framework import routers
from api.views import TelegramUserViewSet, LatestUserDataView
from django.urls import path
from .views import search_telegram_user

urlpatterns = [
    path('search/', search_telegram_user),
    path('last/', LatestUserDataView.as_view()),
]
router = routers.SimpleRouter()
router.register('', TelegramUserViewSet, basename='telegramuser')
urlpatterns += router.urls