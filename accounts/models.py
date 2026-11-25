"""
People and logins (owner: Dan).

User is a custom user model that logs in with email instead of a username.
It has to exist before the very first migration, because Django can't swtich
to a custom user model later without rebuilding the database.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class Department(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """Creates users with email as the login, always stored in lowercase."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required")
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields["role"] != User.Role.ADMIN:
            raise ValueError("A superuser must have the ADMIN role.")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email):
        # Login is case-insensitive: "Thandi@MaforiGroup.co.za" finds thandi@maforigroup.co.za
        return self.get(email__iexact=(email or "").strip())


class User(AbstractUser):
    class Role(models.TextChoices):
        EMPLOYEE = "EMPLOYEE", "Employee"
        AGENT = "AGENT", "IT Agent"
        ADMIN = "ADMIN", "Admin"

    # Email replaces the username completely
    username = None
    email = models.EmailField("email address", unique=True)

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    phone_ext = models.CharField("phone extension", max_length=20, blank=True)
    must_change_password = models.BooleanField(
        default=False, help_text="If set, the user must choose a new password before using the app."
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [
            # Stops two accounts that differ only in letter case
            models.UniqueConstraint(Lower("email"), name="user_email_unique_ci"),
            models.CheckConstraint(
                condition=models.Q(role__in=["EMPLOYEE", "AGENT", "ADMIN"]),
                name="user_role_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        # The admin panel is for the ADMIN role only. Keeping is_staff in step
        # with the role here means nobody can be given admin access by accident
        self.is_staff = self.role == self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_it_staff(self):
        """Agents and admins: can see every ticket and work the queue."""
        return self.is_active and self.role in (self.Role.AGENT, self.Role.ADMIN)

    def __str__(self):
        return self.get_full_name() or self.email
