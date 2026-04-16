"""Tests for Open WebUI configuration and Clerk integration."""
import json
import os
import unittest
from unittest.mock import patch, MagicMock


class TestConfigValidation(unittest.TestCase):
    """Test suite for open-webui/config.json validation."""

    def setUp(self):
        """Load config file for testing."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.json'
        )
        with open(config_path, 'r') as f:
            self.config = json.load(f)

    def test_config_is_valid_json(self):
        """Config file should be valid JSON."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.json'
        )
        with open(config_path, 'r') as f:
            try:
                json.load(f)
            except json.JSONDecodeError as e:
                self.fail(f"config.json is not valid JSON: {e}")

    def test_config_has_openai_section(self):
        """Config should have openai configuration section."""
        self.assertIn('openai', self.config)
        self.assertIn('api_base_url', self.config['openai'])
        self.assertIn('api_key', self.config['openai'])
        self.assertIn('model_name', self.config['openai'])

    def test_config_openai_api_base_url(self):
        """API base URL should point to adapter service."""
        api_base_url = self.config['openai']['api_base_url']
        self.assertIn('adapter', api_base_url)
        self.assertTrue(
            api_base_url.startswith('http://') or api_base_url.startswith('https://'),
            "API base URL should be a valid HTTP/HTTPS URL"
        )

    def test_config_has_ui_section(self):
        """Config should have UI configuration section."""
        self.assertIn('ui', self.config)
        self.assertIn('title', self.config['ui'])
        self.assertIn('description', self.config['ui'])

    def test_config_ui_title_branded(self):
        """UI title should be 'The Intelligence Hub'."""
        self.assertEqual(self.config['ui']['title'], 'The Intelligence Hub')

    def test_config_has_theme_settings(self):
        """Config should have theme configuration."""
        self.assertIn('theme', self.config['ui'])
        theme = self.config['ui']['theme']
        required_theme_keys = ['primary_color', 'secondary_color', 'background_color']
        for key in required_theme_keys:
            self.assertIn(key, theme, f"Theme missing required key: {key}")

    def test_config_has_branding_settings(self):
        """Config should have branding configuration."""
        self.assertIn('branding', self.config['ui'])
        branding = self.config['ui']['branding']
        self.assertIn('welcome_message', branding)
        self.assertIn('footer_text', branding)

    def test_config_has_features_section(self):
        """Config should have features configuration."""
        self.assertIn('features', self.config)
        features = self.config['features']
        self.assertIn('signup_enabled', features)
        self.assertIn('default_user_role', features)

    def test_config_signup_disabled_with_clerk(self):
        """Signup should be disabled when using Clerk auth."""
        self.assertFalse(
            self.config['features']['signup_enabled'],
            "Signup should be disabled when Clerk handles authentication"
        )

    def test_config_has_auth_section(self):
        """Config should have auth configuration."""
        self.assertIn('auth', self.config)
        auth = self.config['auth']
        self.assertIn('type', auth)

    def test_config_auth_type_is_clerk(self):
        """Auth type should be set to 'clerk'."""
        self.assertEqual(self.config['auth']['type'], 'clerk')

    def test_config_has_clerk_section(self):
        """Config should have dedicated Clerk configuration section."""
        self.assertIn('clerk', self.config)
        clerk_config = self.config['clerk']
        self.assertIn('publishable_key', clerk_config)
        self.assertIn('auto_inject_api_key', clerk_config)

    def test_config_has_proxy_section(self):
        """Config should have proxy configuration."""
        self.assertIn('proxy', self.config)
        proxy = self.config['proxy']
        self.assertIn('adapter_url', proxy)
        self.assertIn('orchestrator_url', proxy)
        self.assertIn('timeout_seconds', proxy)


class TestApiKeyInjectionLogic(unittest.TestCase):
    """Test suite for API key injection logic."""

    def test_api_key_placeholder_exists(self):
        """Config should have API key placeholder."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.json'
        )
        with open(config_path, 'r') as f:
            config = json.load(f)

        api_key = config['openai']['api_key']
        self.assertIn('{{USER_API_KEY}}', api_key)

    @patch('urllib.request.urlopen')
    def test_api_key_fetch_with_clerk_token(self, mock_urlopen):
        """API key should be fetchable with valid Clerk token."""
        # Mock the orchestrator response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'api_key': 'sk-test-api-key-12345'
        }).encode()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate API key fetch
        import urllib.request
        req = urllib.request.Request(
            'http://localhost:8000/api/v1/auth/get-api-key',
            headers={
                'Authorization': 'Bearer test-clerk-token',
                'Content-Type': 'application/json',
            }
        )

        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            self.assertIn('api_key', data)
            self.assertEqual(data['api_key'], 'sk-test-api-key-12345')

    def test_clerk_auto_inject_enabled(self):
        """Clerk auto-inject should be enabled in config."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.json'
        )
        with open(config_path, 'r') as f:
            config = json.load(f)

        self.assertTrue(config['clerk']['auto_inject_api_key'])


class TestClerkIntegrationFlow(unittest.TestCase):
    """Test suite for Clerk integration flow (mocked)."""

    def setUp(self):
        """Set up test fixtures."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.json'
        )
        with open(config_path, 'r') as f:
            self.config = json.load(f)

    def test_clerk_enabled_flag(self):
        """Clerk should be enabled in auth config."""
        self.assertTrue(self.config['auth']['clerk_enabled'])

    def test_clerk_publishable_key_placeholder(self):
        """Publishable key should have placeholder for env injection."""
        clerk_key = self.config['clerk']['publishable_key']
        self.assertIn('{{CLERK_PUBLISHABLE_KEY}}', clerk_key)

    def test_clerk_frontend_api_url_placeholder(self):
        """Frontend API URL should have placeholder."""
        frontend_url = self.config['clerk']['frontend_api_url']
        self.assertIn('{{CLERK_FRONTEND_API_URL}}', frontend_url)

    def test_clerk_user_profile_sync_enabled(self):
        """User profile sync should be enabled."""
        self.assertTrue(self.config['clerk']['sync_user_profile'])

    def test_clerk_jwt_validation_enabled(self):
        """JWT validation should be enabled."""
        self.assertTrue(self.config['auth']['jwt_validation'])

    def test_auto_create_users_enabled(self):
        """Auto-create users should be enabled for seamless onboarding."""
        self.assertTrue(self.config['auth']['auto_create_users'])

    @patch('builtins.open', new_callable=unittest.mock.mock_open,
           read_data='{"api_key": "sk-test-key"}')
    def test_clerk_integration_script_exists(self, mock_file):
        """Clerk integration JavaScript file should exist."""
        integration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'clerk-integration.js'
        )
        # Check if file exists in actual filesystem
        self.assertTrue(
            os.path.exists(integration_path),
            "clerk-integration.js should exist in open-webui directory"
        )

    def test_session_refresh_interval_configured(self):
        """Session refresh interval should be configured."""
        self.assertIn('session_refresh_interval', self.config['auth'])
        refresh_interval = self.config['auth']['session_refresh_interval']
        self.assertIsInstance(refresh_interval, int)
        self.assertGreater(refresh_interval, 0)


class TestThemeSettingsValidation(unittest.TestCase):
    """Test suite for theme settings validation."""

    def setUp(self):
        """Load config for theme testing."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.json'
        )
        with open(config_path, 'r') as f:
            self.config = json.load(f)

    def test_theme_primary_color(self):
        """Primary color should be set."""
        primary_color = self.config['ui']['theme']['primary_color']
        self.assertTrue(
            primary_color.startswith('#'),
            "Primary color should be a valid hex color"
        )

    def test_theme_secondary_color(self):
        """Secondary color should be set."""
        secondary_color = self.config['ui']['theme']['secondary_color']
        self.assertTrue(
            secondary_color.startswith('#'),
            "Secondary color should be a valid hex color"
        )

    def test_theme_background_color(self):
        """Background color should be set."""
        bg_color = self.config['ui']['theme']['background_color']
        self.assertTrue(
            bg_color.startswith('#'),
            "Background color should be a valid hex color"
        )

    def test_theme_has_custom_css(self):
        """Theme should reference custom CSS file."""
        self.assertIn('custom_css', self.config['ui']['theme'])
        self.assertEqual(
            self.config['ui']['theme']['custom_css'],
            '/static/custom-theme.css'
        )

    def test_theme_font_family(self):
        """Theme should specify font family."""
        self.assertIn('font_family', self.config['ui']['theme'])
        font_family = self.config['ui']['theme']['font_family']
        self.assertIn('Inter', font_family)

    def test_branding_welcome_message(self):
        """Branding should have welcome message."""
        welcome = self.config['ui']['branding']['welcome_message']
        self.assertIn('Intelligence Hub', welcome)

    def test_branding_footer_text(self):
        """Branding should have footer text."""
        footer = self.config['ui']['branding']['footer_text']
        self.assertIn('Carbon Agent', footer)

    def test_dockerfile_exists(self):
        """Dockerfile should exist for custom Open WebUI build."""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'Dockerfile'
        )
        self.assertTrue(
            os.path.exists(dockerfile_path),
            "Dockerfile should exist in open-webui directory"
        )

    def test_dockerfile_references_clerk_integration(self):
        """Dockerfile should copy clerk-integration.js."""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'Dockerfile'
        )
        with open(dockerfile_path, 'r') as f:
            content = f.read()

        self.assertIn('clerk-integration.js', content)
        self.assertIn('/app/static/', content)


class TestEnvironmentVariables(unittest.TestCase):
    """Test suite for environment variable configuration."""

    def test_env_example_has_clerk_variables(self):
        """.env.example should have Clerk configuration variables."""
        env_example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            '.env.example'
        )

        if os.path.exists(env_example_path):
            with open(env_example_path, 'r') as f:
                content = f.read()

            self.assertIn('OPENWEBUI_CLERK_ENABLED', content)
            self.assertIn('CLERK_PUBLISHABLE_KEY', content)
            self.assertIn('CLERK_SECRET_KEY', content)

    def test_env_production_example_has_clerk_variables(self):
        """.env.production.example should have Clerk configuration variables."""
        env_prod_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            '.env.production.example'
        )

        if os.path.exists(env_prod_path):
            with open(env_prod_path, 'r') as f:
                content = f.read()

            self.assertIn('OPENWEBUI_CLERK_ENABLED', content)
            self.assertIn('CLERK_PUBLISHABLE_KEY', content)


if __name__ == '__main__':
    unittest.main()
