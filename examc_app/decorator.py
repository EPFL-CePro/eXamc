from django.http import Http404


def is_admin(function):
    def wrapper(request, *args, **kwargs):
        if request.user.groups.filter(name="admin").exists():
            return function(request, *args, **kwargs)
        raise Http404

    return wrapper
