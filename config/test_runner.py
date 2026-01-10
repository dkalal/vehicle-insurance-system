from django.conf import settings
from django.test.runner import DiscoverRunner


class ProjectDiscoverRunner(DiscoverRunner):
    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        if not test_labels or test_labels == ['.']:
            test_labels = [
                'apps.accounts.tests.test_rate_limiting',
                'apps.core.tests.test_models_constraints',
                'apps.core.tests.test_tenant_managers',
                'apps.core.tests.test_services',
                'apps.dynamic_fields.tests.test_services',
            ]
        return super().build_suite(test_labels=test_labels, extra_tests=extra_tests, **kwargs)

    def setup_databases(self, **kwargs):
        if getattr(settings, "USE_SQLITE_FOR_TESTS", True):
            settings.DATABASES["default"] = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
                "ATOMIC_REQUESTS": True,
                "CONN_MAX_AGE": 0,
                "OPTIONS": {},
            }
            from django.db import connections

            for alias in connections:
                connections[alias].close()
                if alias in settings.DATABASES:
                    connections[alias].settings_dict.update(settings.DATABASES[alias])
        return super().setup_databases(**kwargs)

    def load_tests_for_label(self, label, discover_kwargs=None):
        if discover_kwargs is None:
            discover_kwargs = {}
        discover_kwargs["top_level_dir"] = settings.BASE_DIR
        return super().load_tests_for_label(label, discover_kwargs)
