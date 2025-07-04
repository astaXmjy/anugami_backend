# contact/models.py
from django.db import models
from customers.models import Customer

class ContactSubmission(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="contact_submissions")
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    subject = models.CharField(max_length=100)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('responded', 'Responded'),
            ('closed', 'Closed')
        ],
        default='pending'
    )
    
    class Meta:
        db_table = 'contact_submissions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subject} - {self.email}"