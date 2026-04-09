from rest_framework.permissions import BasePermission

class IsStaffOrSuperUser(BasePermission):
    """
    Разрешает доступ пользователям с is_staff=True или superuser.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)
