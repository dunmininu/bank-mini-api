from rest_framework.routers import DefaultRouter

from .views import SpeedPayUserViewSet, TransactionViewSet

router = DefaultRouter()
router.register("user", SpeedPayUserViewSet, basename="speedpay-user")
router.register("bank_transaction", TransactionViewSet, basename="bank-transaction")
