from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    @staticmethod
    def normalize_phone_number(phone_number):
        phone_number = str(phone_number).strip()
        return phone_number.replace(' ', '').replace('-', '')

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('وارد کردن شماره تلفن الزامی است.')

        email = extra_fields.get('email')
        if email:
            extra_fields['email'] = self.normalize_email(email)

        phone_number = self.normalize_phone_number(phone_number)
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('کاربر مدیر باید is_staff=True داشته باشد.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('کاربر مدیر باید is_superuser=True داشته باشد.')

        return self.create_user(phone_number, password, **extra_fields)
