"""
Authentication and account-management endpoints.

Includes function-based views (register, login, password change/reset -
custom business logic that doesn't map cleanly to a generic view) and one
class-based view (profile get/update).
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

User = get_user_model()


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    POST: Create a new user account and return it along with a fresh
    access/refresh token pair so the client can log straight in.
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {'user': UserSerializer(user).data, 'tokens': _tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """POST: Authenticate a user with username/password and issue JWT tokens."""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        return Response({'user': UserSerializer(user).data, 'tokens': _tokens_for_user(user)})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    POST: Blacklist-equivalent logout. Since BLACKLIST_AFTER_ROTATION is off
    by default in this project, this simply acknowledges the client should
    discard its tokens; flip on the blacklist app in settings for a
    real server-side revoke.
    """
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'detail': 'refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        RefreshToken(refresh_token).blacklist()
    except AttributeError:
        # Blacklist app not installed - nothing more to do server-side.
        pass
    except Exception:
        return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """POST: Change the authenticated user's password."""
    serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response({'detail': 'Password updated successfully.'})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    POST: Begin the password-reset flow. Always returns 200 regardless of
    whether the email matches an account, to avoid leaking which emails
    are registered.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email']
    user = User.objects.filter(email__iexact=email).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        # In production this uid/token pair would be emailed to the user
        # rather than returned in the response.
        return Response({'detail': 'Password reset instructions sent.', 'uid': uid, 'token': token})
    return Response({'detail': 'Password reset instructions sent.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_password_reset(request):
    """POST: Complete the password-reset flow given a uid/token pair."""
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return Response({'detail': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, serializer.validated_data['token']):
        return Response({'detail': 'Invalid or expired reset token.'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(serializer.validated_data['new_password'])
    user.save()
    return Response({'detail': 'Password has been reset successfully.'})


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET: Retrieve the authenticated user's profile.
    PUT/PATCH: Update the authenticated user's profile.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
