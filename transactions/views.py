from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.views.generic import CreateView, ListView
from transactions.constants import DEPOSIT, WITHDRAWAL,LOAN, LOAN_PAID
from datetime import datetime
from django.db.models import Sum
from transactions.forms import (
    DepositForm,
    WithdrawForm,
    LoanRequestForm,
    TransferMoneyForm
)
from transactions.models import Transaction
from django.shortcuts import render
from accounts.models import UserBankAccount
from .constants import TRANSFER_MONEY
import sweetify
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string


class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transactions/transaction_form.html'
    model = Transaction
    title = ''
    success_url = reverse_lazy('transaction_report')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'account': self.request.user.account
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs) # template e context data pass kora
        context.update({
            'title': self.title
        })

        return context


class DepositMoneyView(TransactionCreateMixin):
    form_class = DepositForm
    title = 'Deposit'

    def get_initial(self):
        initial = {'transaction_type': DEPOSIT}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        account = self.request.user.account
        # if not account.initial_deposit_date:
        #     now = timezone.now()
        #     account.initial_deposit_date = now
        account.balance += amount # amount = 200, tar ager balance = 0 taka new balance = 0+200 = 200
        account.save(
            update_fields=[
                'balance'
            ]
        )

        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was deposited to your account successfully'
        )

        mail_subject='Deposit message'
        message=render_to_string('transactions/deposit_mail.html',{
            'user': self.request.user,
            'amount': amount
        })
        to_email=self.request.user.email
        send_email=EmailMultiAlternatives(mail_subject,'',to=[to_email])
        send_email.attach_alternative(message,'text/html')
        send_email.send()
        return super().form_valid(form)


class WithdrawMoneyView(TransactionCreateMixin):
    form_class = WithdrawForm
    title = 'Withdraw Money'

    def get_initial(self):
        initial = {'transaction_type': WITHDRAWAL}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        
        if self.request.user.account.is_bankrupt:
            # messages.error(self.request, 'The mamar bank is  bankrupt')
            sweetify.error(self.request, "Mamar Bank Bankrupt", timer=6000)
            return redirect('home')
        else:
            self.request.user.account.balance -= form.cleaned_data.get('amount')
            # balance = 300
            # amount = 5000
            self.request.user.account.save(update_fields=['balance'])

            messages.success(
                self.request,
                f'Successfully withdrawn {"{:,.2f}".format(float(amount))}$ from your account'
            )
            mail_subject='Withdrawal message'
            message=render_to_string('transactions/withdraw_mail.html',{
                'user': self.request.user,
                'amount': amount
            })
            to_email=self.request.user.email
            send_email=EmailMultiAlternatives(mail_subject,'',to=[to_email])
            send_email.attach_alternative(message,'text/html')
            send_email.send()

            return super().form_valid(form)

class LoanRequestView(TransactionCreateMixin):
    form_class = LoanRequestForm
    title = 'Request For Loan'

    def get_initial(self):
        initial = {'transaction_type': LOAN}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        current_loan_count = Transaction.objects.filter(
            account=self.request.user.account,transaction_type=3,loan_approve=True).count()
        if current_loan_count >= 3:
            return HttpResponse("You have cross the loan limits")
        messages.success(
            self.request,
            f'Loan request for {"{:,.2f}".format(float(amount))}$ submitted successfully'
        )
        mail_subject='Loan Request message'
        message=render_to_string('transactions/loan_mail.html',{
                'user': self.request.user,
                'amount': amount
            })
        to_email=self.request.user.email
        send_email=EmailMultiAlternatives(mail_subject,'',to=[to_email])
        send_email.attach_alternative(message,'text/html')
        send_email.send()
            

        return super().form_valid(form)
    
class TransactionReportView(LoginRequiredMixin, ListView):
    template_name = 'transactions/transaction_report.html'
    model = Transaction
    balance = 0 # filter korar pore ba age amar total balance ke show korbe
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(
            account=self.request.user.account
        )
        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            queryset = queryset.filter(timestamp__date__gte=start_date, timestamp__date__lte=end_date)
            self.balance = Transaction.objects.filter(
                timestamp__date__gte=start_date, timestamp__date__lte=end_date
            ).aggregate(Sum('amount'))['amount__sum']
        else:
            self.balance = self.request.user.account.balance
       
        return queryset.distinct() # unique queryset hote hobe
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account': self.request.user.account
        })

        return context
    
        
class PayLoanView(LoginRequiredMixin, View):
    def get(self, request, loan_id):
        loan = get_object_or_404(Transaction, id=loan_id)
        print(loan)
        if loan.loan_approve:
            user_account = loan.account
                # Reduce the loan amount from the user's balance
                # 5000, 500 + 5000 = 5500
                # balance = 3000, loan = 5000
            if loan.amount < user_account.balance:
                user_account.balance -= loan.amount
                loan.balance_after_transaction = user_account.balance
                user_account.save()
                loan.loan_approved = True
                loan.transaction_type = LOAN_PAID
                loan.save()
                return redirect('loan_list')
            else:
                messages.error(
            self.request,
            f'Loan amount is greater than available balance'
        )

        return redirect('loan_list')


class LoanListView(LoginRequiredMixin,ListView):
    model = Transaction
    template_name = 'transactions/loan_request.html'
    context_object_name = 'loans' # loan list ta ei loans context er moddhe thakbe
    
    def get_queryset(self):
        user_account = self.request.user.account
        queryset = Transaction.objects.filter(account=user_account,transaction_type=3)
        print(queryset)
        return queryset


class TransferMoneyView(LoginRequiredMixin, View):
    template_name='transactions/transfer_money.html'
    form_class=TransferMoneyForm
    
    def get(self,request):
        return render(request,self.template_name, {'form':self.form_class()})
    
    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            to_account_number = form.cleaned_data['account_number']
            print(to_account_number, amount)
            # from_account_number=self.request.user.account.account_no
            # print(to_account_number, from_account_number)
            account_query=UserBankAccount.objects.get(account_no=to_account_number)
            if account_query:
                account_query.balance += amount
                account_query.save()
                self.request.user.account.balance -= amount
                self.request.user.account.save()
                Transaction.objects.create(
                    account=self.request.user.account,
                    amount=amount,
                    balance_after_transaction=self.request.user.account.balance,
                    transaction_type=TRANSFER_MONEY,
                   
                )
                Transaction.objects.create(
                    account=account_query,
                    amount=amount,
                    balance_after_transaction=account_query.balance,
                    transaction_type=TRANSFER_MONEY,
                    
                )
                
                
                messages.success(request, 'Money transferred successfully')
                return redirect('transaction_report')
                
            else:
                messages.error(request, 'Invalid account number')
                
           
        else:
            return render(request, self.template_name, {'form': form})