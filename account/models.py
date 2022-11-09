import uuid as uuid_lib
import warnings
import secrets
from datetime import datetime

from django.db import models
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager, PermissionsMixin
from django.utils import timezone


# Create your models here.

TODAY = datetime.now
NOT_PROVIDED = object()  # RemovedInDjango40Warning.


def get_random_int(
    length=NOT_PROVIDED,
    allowed_chars=("0123456789"),
):
    """
    Return a securely generated random int.

    The bit length of the returned value can be calculated with the formula:
        log_2(len(allowed_chars)^length)

    """
    if length is NOT_PROVIDED:
        length = 10
    return "".join(secrets.choice(allowed_chars) for i in range(length))


class EmailAddress(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid_lib.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="email_addresses",
        on_delete=models.CASCADE,
    )
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

    def confirm(self):
        self.is_verified = True
        self.save(update_fields=["is_verified"])
        self.user.save()


class MyUserManager(BaseUserManager):
    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_staff", True)

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class SpeedPayUser(AbstractBaseUser, PermissionsMixin):
    uuid = models.UUIDField(unique=True, default=uuid_lib.uuid4)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=50, default="oluwaseyi")
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)
    is_staff = models.BooleanField(default=False)

    objects = MyUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELD = []

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True


class BankAccount(models.Model):
    user = models.ForeignKey(
        SpeedPayUser, on_delete=models.CASCADE, related_name="user_bank_account"
    )
    account_number = models.IntegerField(default=0)
    account_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.account_number)

    def generate_account_number(self, commit=False):
        self.account_number = get_random_int(length=10)

        if commit:
            self.save(update_fields=["account_number"])

    def deposit(self, amount):
        amount = amount
        new_balance = self.account_balance + amount

        return new_balance

    def withdraw(self, amount):
        amount = amount
        new_balance = self.account_balance - amount

        return new_balance


class TransactionTypeChoices(models.TextChoices):
    WITHDRAW = ("Withdraw", "withdraw")
    DEPOSIT = ("Deposit", "deposit")


class Transaction(models.Model):
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="bank_transaction"
    )
    transaction_id = models.CharField(max_length=15)
    transaction_type = models.CharField(
        max_length=20, choices=TransactionTypeChoices.choices
    )
    amount = models.PositiveIntegerField(default=0.00)

    def generate_transaction_number(self, commit=False):
        self.transaction_id = get_random_int(length=15)

        if commit:
            self.save(update_fields=["transaction_id"])
