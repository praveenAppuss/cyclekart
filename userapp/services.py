# userapp/services.py
from django.db import transaction
from .models import Wallet, WalletTransaction

class WalletService:
    @staticmethod
    def add_balance(wallet, amount, description="", order=None):
        """Add amount to wallet and create a transaction."""
        with transaction.atomic():
            if amount <= 0:
                raise ValueError("Amount must be positive")
            wallet.balance += amount
            wallet.save(update_fields=['balance', 'updated_at'])
            WalletTransaction.objects.create(
                wallet=wallet,
                order=order,
                amount=amount,
                transaction_type='credit',
                description=description
            )
        return wallet

    @staticmethod
    def deduct_balance(wallet, amount, description="", order=None):
        """Deduct amount from wallet and create a transaction."""
        with transaction.atomic():
            if amount <= 0:
                raise ValueError("Amount must be positive")
            if wallet.balance >= amount:
                wallet.balance -= amount
                wallet.save(update_fields=['balance', 'updated_at'])
                WalletTransaction.objects.create(
                    wallet=wallet,
                    order=order,
                    amount=amount,
                    transaction_type='debit',
                    description=description
                )
                return wallet
            else:
                raise ValueError("Insufficient balance")