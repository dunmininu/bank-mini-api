from django.contrib.auth import get_user_model, password_validation, authenticate
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from rest_framework import serializers

from .models import SpeedPayUser, BankAccount, Transaction

User = get_user_model()
INVALID_CREDENTIALS_MSG = "Unable to login with the provided credentials."


def validate_user_password_attribute_similarity(password, user):
    if settings.DEBUG:
        return

    try:
        validator = password_validation.UserAttributeSimilarityValidator()
        validator.validate(password, user)
    except ValidationError as e:
        raise serializers.ValidationError({"password": e.messages})


class SpeedPayUserRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField()
    date_of_birth = serializers.DateField()
    password = serializers.CharField(min_length=8, max_length=128)

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate_email(self, value):
        if SpeedPayUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists")
        return value

    @transaction.atomic
    def save(self):
        email = self.validated_data["email"]
        name = self.validated_data["name"]
        date_of_birth = self.validated_data["date_of_birth"]
        password = self.validated_data["password"]

        user = User(email=email, name=name, date_of_birth=date_of_birth)
        user.set_password(password)
        validate_user_password_attribute_similarity(password, user)
        user.save()
        return user


class BankAccountDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "user",
            "account_number",
            "account_balance",
            "created_at",
        ]


class BankAccountCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "user",
        ]

    def to_representation(self, instance):
        return BankAccountDetailSerializer(instance=instance, context=self.context).data


class UserDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeedPayUser
        fields = ["id", "email", "name", "date_of_birth"]


class UserDetailsTokenSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserDetailsSerializer()
    bank_account = BankAccountDetailSerializer()


class TransactionSerializer(serializers.ModelSerializer):
    amount = serializers.IntegerField()

    class Meta:
        model = Transaction
        fields = [
            "bank_account",
            "transaction_type",
            "amount",
        ]


class TransactionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "bank_account",
            "transaction_id",
            "transaction_type",
            "amount",
        ]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128)

    def authenticate_user(self, request, **data):
        user = authenticate(request, **data)
        if not user:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [INVALID_CREDENTIALS_MSG],
                    "code": "invalid_credentials",
                }
            )

        return user

    def validate_email_address(self, user):
        email_address = user.email_addresses.filter(email=user.email).first()
        if not email_address or (email_address and not email_address.is_verified):
            msg = "You have to verify your email before you can login."
            raise serializers.ValidationError(
                {
                    "detail": msg,
                    "code": "email_not_verified",
                }
            )

    def save(self):
        user = self.authenticate_user(self.context["request"], **self.validated_data)

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(max_length=1000)
