from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.db import transaction
from django.http import HttpResponse

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from drf_yasg.utils import swagger_auto_schema

from .serializers import (
    UserDetailsTokenSerializer,
    SpeedPayUserRegisterSerializer,
    UserDetailsSerializer,
    TransactionSerializer,
    TransactionDetailSerializer,
    LoginSerializer,
    LogoutSerializer,
)
from .models import (
    SpeedPayUser,
    BankAccount,
    EmailAddress,
    Transaction,
)

# Create your views here.
User = get_user_model()


class UserTokenResponseMixin:
    def get_user_token_response_data(self, user, bank_account):
        refresh_token = RefreshToken.for_user(user)
        access_token = refresh_token.access_token

        access_token.set_exp(lifetime=timedelta(seconds=settings.WEB_TOKEN_EXPIRY))

        data = {
            "access_token": str(access_token),
            "refresh_token": str(refresh_token),
            "user": user,
            "bank_account": bank_account,
        }

        return UserDetailsTokenSerializer(data, context={"request": self.request}).data


class SpeedPayUserViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
    UserTokenResponseMixin,
):
    queryset = SpeedPayUser.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return SpeedPayUserRegisterSerializer
        elif self.action == "list_of_users":
            return UserDetailsTokenSerializer
        elif self.action == "login":
            return LoginSerializer
        elif self.action == "logout":
            return LogoutSerializer

    @transaction.atomic
    @swagger_auto_schema(
        request_body=SpeedPayUserRegisterSerializer,
        responses={status.HTTP_200_OK: UserDetailsTokenSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        EmailAddress.objects.create(
            user=user, email=user.email, is_primary=True, is_verified=True
        )
        bank_account = BankAccount.objects.create(
            user=user,
        )
        bank_account.generate_account_number()
        bank_account.save()

        data = self.get_user_token_response_data(user, bank_account)
        return Response(data=data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def list_of_users(self, request, *args, **kwargs):
        account_qs = BankAccount.objects.all()
        user_qs = User.objects.all().values(
            "id",
            "uuid",
            "email",
            "name",
            "date_of_birth",
        )

        list_user_n_accounts = []
        data = {}

        for user in user_qs:
            account_details = account_qs.filter(user=user["id"]).values(
                "account_number",
                "account_balance",
                "created_at",
            )

        data["user"] = user
        data["account_details"] = account_details

        list_user_n_accounts.append(data)

        data = {"list_of_users": list_user_n_accounts}
        return Response(data=data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(request_body=LoginSerializer)
    @transaction.atomic
    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def login(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        email_addr = EmailAddress.objects.get(email=user.email)
        if not email_addr.is_verified:
            email_addr.confirm()

        bank_account = BankAccount.objects.get(user=user)

        data = {
            "user": self.get_user_token_response_data(user, bank_account),
        }
        return Response(data=data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(request_body=LogoutSerializer)
    @transaction.atomic
    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def logout(self, request, *args, **kwargs):
        response = Response(
            {"detail": "Successfully logged out."}, status=status.HTTP_200_OK
        )
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except serializers.ValidationError as e:
            response.data = e.detail
            response.status_code = status.HTTP_401_UNAUTHORIZED
        except (TokenError, AttributeError, TypeError):
            response.data = {"detail": "Token is blacklisted or invalid or expired."}
            response.status_code = status.HTTP_401_UNAUTHORIZED
        return response


class TransactionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Transaction.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return TransactionSerializer
        elif self.action in ["list", "retrieve"]:
            return TransactionDetailSerializer

    @transaction.atomic
    @swagger_auto_schema(
        request_body=TransactionSerializer,
        responses={status.HTTP_200_OK: TransactionDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()

        if transaction.transaction_type == "Deposit":
            bank_account = transaction.bank_account
            amount = serializer["amount"]

            update_balance = bank_account.account_balance + Decimal(amount.value)
            new_balance = BankAccount.objects.update(account_balance=update_balance)
            transaction = Transaction.objects.get(id=transaction.id)
            transaction.generate_transaction_number()
            transaction.save()
            data = {
                "transaction": transaction.transaction_id,
                "message": "transaction successful",
                "new_balance": new_balance.account_balance,
            }
            return Response(data=data, status=status.HTTP_201_CREATED)

        elif transaction.transaction_type == "Withdraw":
            bank_account = transaction.bank_account
            amount = serializer["amount"]

            if amount.value > bank_account.account_balance:
                return HttpResponse("Insufficient funds")
            else:
                update_balance = bank_account.account_balance - Decimal(amount.value)
            BankAccount.objects.update(account_balance=update_balance)
            new_balance = bank_account.account_balance
            transaction = Transaction.objects.get(id=transaction.id)
            transaction.generate_transaction_number()
            transaction.save()
            print(dir(new_balance))
            data = {
                "transaction": transaction.transaction_id,
                "message": "transaction successful",
                "new_balance": new_balance,
            }
            return Response(data=data, status=status.HTTP_201_CREATED)
