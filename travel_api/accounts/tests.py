"""Tests for registration, login, profile and password management."""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class RegistrationTests(APITestCase):
    """Test account registration."""

    def setUp(self):
        self.url = reverse('accounts:register')
        self.valid_payload = {
            'username': 'traveler1',
            'email': 'traveler1@example.com',
            'password': 'StrongPass123',
            'password_confirm': 'StrongPass123',
            'first_name': 'Ada',
            'last_name': 'Lovelace',
        }

    def test_register_success(self):
        """A valid payload creates a user and returns JWT tokens."""
        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data['tokens'])
        self.assertEqual(User.objects.count(), 1)

    def test_register_password_mismatch(self):
        """Mismatched password confirmation is rejected."""
        payload = {**self.valid_payload, 'password_confirm': 'Different123'}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email(self):
        """Registering twice with the same email fails."""
        self.client.post(self.url, self.valid_payload)
        response = self.client.post(self.url, {**self.valid_payload, 'username': 'other'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    """Test login and token issuance."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='loginuser', email='login@example.com', password='TestPass123'
        )
        self.url = reverse('accounts:login')

    def test_login_success(self):
        response = self.client.post(self.url, {'username': 'loginuser', 'password': 'TestPass123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['tokens'])

    def test_login_invalid_credentials(self):
        response = self.client.post(self.url, {'username': 'loginuser', 'password': 'wrong'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProfileTests(APITestCase):
    """Test profile retrieval and update."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='profileuser', email='profile@example.com', password='TestPass123'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:profile')

    def test_get_profile(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'profileuser')

    def test_update_profile(self):
        response = self.client.patch(self.url, {'bio': 'Loves mountains'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, 'Loves mountains')

    def test_profile_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordChangeTests(APITestCase):
    """Test authenticated password change."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='pwuser', email='pw@example.com', password='OldPass123'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:password-change')

    def test_change_password_success(self):
        response = self.client.post(self.url, {
            'old_password': 'OldPass123',
            'new_password': 'NewPass456',
            'new_password_confirm': 'NewPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456'))

    def test_change_password_wrong_old_password(self):
        response = self.client.post(self.url, {
            'old_password': 'WrongOld',
            'new_password': 'NewPass456',
            'new_password_confirm': 'NewPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutTests(APITestCase):
    """Test the logout endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='logoutuser', email='logout@example.com', password='TestPass123'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:logout')

    def test_logout_requires_refresh_token(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_with_refresh_token(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(self.url, {'refresh': str(refresh)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_with_garbage_token(self):
        response = self.client.post(self.url, {'refresh': 'not-a-real-token'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, {'refresh': 'irrelevant'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetFlowTests(APITestCase):
    """Test the request-reset / confirm-reset password flow."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='resetuser', email='reset@example.com', password='OldPass123'
        )
        self.request_url = reverse('accounts:password-reset-request')
        self.confirm_url = reverse('accounts:password-reset-confirm')

    def test_request_reset_for_known_email_returns_uid_and_token(self):
        response = self.client.post(self.request_url, {'email': 'reset@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('uid', response.data)
        self.assertIn('token', response.data)

    def test_request_reset_for_unknown_email_still_returns_200(self):
        response = self.client.post(self.request_url, {'email': 'nobody@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('uid', response.data)

    def test_confirm_reset_with_valid_token_changes_password(self):
        request_response = self.client.post(self.request_url, {'email': 'reset@example.com'})
        uid = request_response.data['uid']
        token = request_response.data['token']
        response = self.client.post(self.confirm_url, {
            'uid': uid, 'token': token, 'new_password': 'BrandNewPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPass456'))

    def test_confirm_reset_with_invalid_token_fails(self):
        request_response = self.client.post(self.request_url, {'email': 'reset@example.com'})
        uid = request_response.data['uid']
        response = self.client.post(self.confirm_url, {
            'uid': uid, 'token': 'bogus-token', 'new_password': 'BrandNewPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_reset_with_invalid_uid_fails(self):
        response = self.client.post(self.confirm_url, {
            'uid': 'not-a-valid-uid', 'token': 'whatever', 'new_password': 'BrandNewPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

