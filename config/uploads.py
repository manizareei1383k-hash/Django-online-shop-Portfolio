from io import BytesIO
from pathlib import Path
import uuid
import warnings

from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.utils.deconstruct import deconstructible
from PIL import Image, UnidentifiedImageError


class LimitedUploadHandler(FileUploadHandler):
    def __init__(self, request=None):
        super().__init__(request)
        self.total_received = 0

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.received = 0

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        self.total_received += len(raw_data)
        if self.received > settings.MAX_UPLOAD_BYTES or self.total_received > settings.MAX_REQUEST_BYTES:
            self.request.upload_limit_exceeded = True
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None


@deconstructible
class PrivateTicketStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return str(Path(settings.PRIVATE_MEDIA_ROOT).resolve())

    def url(self, name):
        from django.urls import reverse
        return reverse('account:ticket_attachment_file', kwargs={'name': name})


private_ticket_storage = PrivateTicketStorage()


class SafeImageFormMixin:
    def clean(self):
        cleaned = super().clean()
        for name, field in self.fields.items():
            if isinstance(field, forms.ImageField) and cleaned.get(name):
                try:
                    cleaned[name] = clean_image_upload(cleaned[name])
                except forms.ValidationError as error:
                    self.add_error(name, error)
        return cleaned


def ticket_upload_path(instance, filename):
    return f'tickets/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


def clean_image_upload(upload):
    if not upload or not hasattr(upload, 'content_type'):
        return upload
    if upload.size > settings.MAX_UPLOAD_BYTES:
        raise forms.ValidationError('حجم فایل نباید بیشتر از ۵ مگابایت باشد.')
    try:
        upload.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as picture:
                if picture.format not in {'JPEG', 'PNG', 'GIF', 'WEBP'}:
                    raise forms.ValidationError('فرمت تصویر مجاز نیست.')
                if picture.width * picture.height > 16_000_000:
                    raise forms.ValidationError('ابعاد تصویر بیش از حد مجاز است.')
                picture.load()
                result = BytesIO()
                picture.convert('RGB').save(result, format='JPEG', quality=90)
        data = result.getvalue()
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise forms.ValidationError('حجم تصویر بیش از حد مجاز است.')
        return ContentFile(data, name=f'{uuid.uuid4().hex}.jpg')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise forms.ValidationError('تصویر معتبر نیست.')


def clean_ticket_upload(upload):
    if not upload or not hasattr(upload, 'content_type'):
        return upload
    if upload.size > settings.MAX_UPLOAD_BYTES:
        raise forms.ValidationError('حجم فایل نباید بیشتر از ۵ مگابایت باشد.')
    suffix = Path(upload.name).suffix.lower()
    if suffix in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
        return clean_image_upload(upload)
    upload.seek(0)
    if suffix == '.pdf' and upload.read(5) == b'%PDF-':
        upload.seek(0)
        return upload
    raise forms.ValidationError('فقط تصویر معتبر یا فایل PDF مجاز است.')
