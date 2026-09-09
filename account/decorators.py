from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view_function):
    @login_required
    @wraps(view_function)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied
        return view_function(request, *args, **kwargs)

    return wrapped_view
