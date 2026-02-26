from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from faker import Faker
import random
from datetime import timedelta

from book.models import Author, Genre, Book, BookInstance, Borrowing


class Command(BaseCommand):
    help = "Seed fake data for the library system"

    def add_arguments(self, parser):
        parser.add_argument("--authors", type=int, default=25)
        parser.add_argument("--genres", type=int, default=12)
        parser.add_argument("--books", type=int, default=60)
        parser.add_argument("--users", type=int, default=30)
        parser.add_argument("--borrowings", type=int, default=40)

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.fake = Faker("en_PH")

        authors_n = kwargs["authors"]
        genres_n = kwargs["genres"]
        books_n = kwargs["books"]
        users_n = kwargs["users"]
        borrowings_n = kwargs["borrowings"]

        self.create_authors(authors_n)
        self.create_genres(genres_n)
        self.create_users(users_n)
        self.create_books_and_instances(books_n)
        self.create_borrowings(borrowings_n)

        self.stdout.write(self.style.SUCCESS("✅ Library seed complete."))

    def create_authors(self, count):
        created = 0
        for _ in range(count):
            Author.objects.create(
                first_name=self.fake.first_name(),
                last_name=self.fake.last_name(),
                date_of_birth=self.fake.date_of_birth(minimum_age=25, maximum_age=90),
                date_of_death=None if random.random() < 0.8 else self.fake.date_between(start_date="-20y", end_date="today"),
                biography=self.fake.text(max_nb_chars=250),
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created} authors."))

    def create_genres(self, count):
        base = [
            "Fiction", "Non-Fiction", "Fantasy", "Sci-Fi", "Mystery", "Thriller",
            "Romance", "History", "Biography", "Self-Help", "Technology", "Science",
            "Philosophy", "Psychology", "Horror", "Comics"
        ]
        random.shuffle(base)

        created = 0
        for name in base[:count]:
            obj, was_created = Genre.objects.get_or_create(
                name=name,
                defaults={"description": self.fake.sentence()}
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} genres (or already existed)."))

    def create_users(self, count):
        created = 0
        for _ in range(count):
            username = self.fake.unique.user_name()
            User.objects.create_user(
                username=username,
                email=self.fake.unique.email(),
                password="password123"  
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} users (borrowers)."))

    def create_books_and_instances(self, count):
        authors = list(Author.objects.all())
        genres = list(Genre.objects.all())

        if not authors:
            self.stdout.write(self.style.ERROR("No authors found. Seed authors first."))
            return

        created_books = 0
        created_instances = 0

        for _ in range(count):
            total_copies = random.randint(1, 6)

            book = Book.objects.create(
                title=self.fake.sentence(nb_words=4).rstrip("."),
                isbn=self.fake.unique.isbn13().replace("-", "")[:13],  
                publication_year=self.fake.random_int(1980, 2025),
                description=self.fake.text(max_nb_chars=400),
                total_copies=total_copies,
                available_copies=total_copies, 
            )

            book.authors.set(random.sample(authors, k=random.randint(1, min(3, len(authors)))))

            if genres and random.random() < 0.85:
                book.genres.set(random.sample(genres, k=random.randint(1, min(3, len(genres)))))

            for _i in range(total_copies):
                BookInstance.objects.create(
                    book=book,
                    condition=random.choice(["excellent", "good", "fair", "damaged"]),
                    is_available=True,

                )
                created_instances += 1

            created_books += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created_books} books."))
        self.stdout.write(self.style.SUCCESS(f"Created {created_instances} book instances."))

    def create_borrowings(self, count):
        users = list(User.objects.all())
        available_instances = list(BookInstance.objects.filter(is_available=True))

        if not users:
            self.stdout.write(self.style.ERROR("No users found. Seed users first."))
            return
        if not available_instances:
            self.stdout.write(self.style.ERROR("No available book instances found. Seed instances first."))
            return

        created = 0
        tries = 0
        max_tries = count * 10

        while created < count and tries < max_tries:
            tries += 1

            if not available_instances:
                available_instances = list(BookInstance.objects.filter(is_available=True))
                if not available_instances:
                    break

            instance = random.choice(available_instances)
            borrower = random.choice(users)

            borrow_dt = self.fake.date_time_between(start_date="-120d", end_date="now", tzinfo=timezone.get_current_timezone())
            due_date = (borrow_dt + timedelta(days=random.randint(7, 21))).date()

            borrowing = Borrowing.objects.create(
                book_instance=instance,
                borrower=borrower,
                borrow_date=borrow_dt,
                due_date=due_date,
                is_returned=False,
                fine=0.00,
            )

            if random.random() < 0.55:
                borrowing.mark_as_returned()

            available_instances = [bi for bi in available_instances if bi.id != instance.id]

            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} borrowing records."))