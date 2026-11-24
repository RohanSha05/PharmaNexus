from functools import wraps
from rest_framework.exceptions import PermissionDenied

def roles(*allowed):
 def decorator(fn):
  @wraps(fn)
  def wrapped(request,*args,**kwargs):
   if not(request.user.is_superuser or request.user.groups.filter(name__in=allowed).exists()): raise PermissionDenied('Your role cannot perform this action')
   return fn(request,*args,**kwargs)
  return wrapped
 return decorator
