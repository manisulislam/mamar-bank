from django.contrib import admin
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
# from transactions.models import Transaction
from .models import Transaction
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['account', 'amount', 'balance_after_transaction', 'transaction_type', 'loan_approve']
    
    def save_model(self, request, obj, form, change):
        obj.account.balance += obj.amount
        obj.balance_after_transaction = obj.account.balance
        obj.account.save()
        mail_subject='Loan Approve Message'
        message=render_to_string('transactions/admin_mail.html',{
                'user': obj.account.user,
                'amount': obj.amount
            })
        to_email=obj.account.user.email
        send_email=EmailMultiAlternatives(mail_subject,'',to=[to_email])
        send_email.attach_alternative(message,'text/html')
        send_email.send()
        super().save_model(request, obj, form, change)

