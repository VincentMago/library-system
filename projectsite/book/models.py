from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator


class Author(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_death = models.DateField(null=True, blank=True)
    biography = models.TextField(blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "genres"

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255)
    isbn = models.CharField(max_length=13, unique=True, blank=True, null=True)  # ISBN-13
    publication_year = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='book_covers/', null=True, blank=True)
    
    authors = models.ManyToManyField(Author, related_name='books')
    genres = models.ManyToManyField(Genre, related_name='books', blank=True)
    
    total_copies = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    available_copies = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Keep available_copies ≤ total_copies
        if self.available_copies > self.total_copies:
            self.available_copies = self.total_copies
        super().save(*args, **kwargs)


class BookInstance(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='instances')
    inventory_number = models.CharField(max_length=20, unique=True, blank=True)  # e.g. "LIB-001-2025"
    condition = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('damaged', 'Damaged'),
        ],
        default='good'
    )
    is_available = models.BooleanField(default=True)
    added_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['book', 'inventory_number']

    def __str__(self):
        return f"{self.book.title} - {self.inventory_number or 'no inv#'}"

    def save(self, *args, **kwargs):
        if not self.inventory_number:
            # Simple auto-numbering example — improve later if needed
            last = BookInstance.objects.filter(book=self.book).order_by('id').last()
            num = 1 if not last else int(last.inventory_number.split('-')[-1]) + 1
            self.inventory_number = f"{self.book.id:03d}-{num:04d}"
        super().save(*args, **kwargs)


class Borrowing(models.Model):
    book_instance = models.ForeignKey(BookInstance, on_delete=models.PROTECT, related_name='borrowings')
    borrower = models.ForeignKey(User, on_delete=models.PROTECT, related_name='borrowings')
    
    borrow_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    return_date = models.DateTimeField(null=True, blank=True)
    
    is_returned = models.BooleanField(default=False)
    fine = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, help_text="Overdue fine if any")

    class Meta:
        ordering = ['-borrow_date']

    def __str__(self):
        return f"{self.borrower.username} - {self.book_instance}"

    def save(self, *args, **kwargs):
        if not self.pk:  # new borrowing
            if self.book_instance.is_available:
                self.book_instance.is_available = False
                self.book_instance.book.available_copies -= 1
                self.book_instance.book.save()
                self.book_instance.save()
            else:
                raise ValueError("This book copy is not available!")
        super().save(*args, **kwargs)

    def mark_as_returned(self):
        if not self.is_returned:
            self.is_returned = True
            self.return_date = timezone.now()
            self.book_instance.is_available = True
            self.book_instance.book.available_copies += 1
            self.book_instance.book.save()
            self.book_instance.save()
            self.save()
