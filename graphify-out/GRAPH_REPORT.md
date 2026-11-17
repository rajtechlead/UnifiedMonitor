# Graph Report - cbb7236d17c7b011ebaca937  (2026-11-17)

## Corpus Check
- 201 files · ~105,650 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: (none) 7, .example 2, .ini 2)

## Summary
- 3425 nodes · 6922 edges · 201 communities (143 shown, 58 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 431 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a95d73e3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- asyncio
- .get
- Tenant
- typing
- AIRemediationEngine
- dashboard.py
- NotificationDispatcher
- AsyncClient
- test_core_logging.py
- FindingRepository
- logging.py
- test_providers.py
- annotations
- test_worker_tasks.py
- package.json
- setup_wizard.py
- security.py
- _make_engine
- test_auth_and_cli.py
- conftest.py
- grc.py
- data
- test_api_auth.py
- AssessmentRun
- GraphClient
- SecretMetadata
- reports.py
- controls
- Tenant
- _run
- ControlLoader
- FrameworkCrosswalk
- LocalVaultProvider
- CloudDashboard.tsx
- auth.py
- _run
- AssessmentRun
- main.py
- App.tsx
- cli.py
- controls
- controls
- controls
- controls
- controls
- core/cache.py
- AzureKeyVaultProvider
- get_current_user
- get_secret_resolver
- controls
- controls
- controls
- monitoring.py
- v1/notifications.py
- crosswalk.py
- SecretCache
- compliance_mapping
- compilerOptions
- main
- _run
- SecretAuditLog
- controls
- BaseRepository
- _parse_legacy_format
- Settings
- controls
- get_settings
- controls
- compute_score
- test_extended_collectors.py
- ports
- CsvReportGenerator
- smoke_test.py
- NotificationDispatcher
- BaseReportGenerator
- @tanstack/react-query
- resolver.py
- TestLoginJourney
- _normalise
- engine.py
- @playwright/test
- SecretProvider
- ExcelReportGenerator
- require_role
- controls
- controls
- controls
- labels
- dependencies.py
- env.py
- containers
- labels
- containers
- ErrorBoundary
- hooks
- AsyncClient
- ControlDefinition
- test_reporting.py
- services
- db
- containers
- scripts
- setup.py
- TestFindingsJourney
- TestDashboardJourney
- test_reporting.py
- _parse_list_format
- controls
- beat
- healthcheck
- unimonitor
- spec
- labels
- spec
- controls
- AsyncClient
- worker
- namespace.yaml
- PersistentVolumeClaim unimonitor-redis-data
- template
- AssessmentsPage.tsx
- ExecutiveDashboard.tsx
- compilerOptions
- TestReportsJourney
- TestTenantJourney
- test_windows_build_assets.py
- redis
- Deployment unimonitor-api
- spec
- service.yaml
- Deployment unimonitor-beat
- test_cloud_providers.py
- CisoDashboard.tsx
- CloudProviderPage.tsx
- controls
- db
- initContainers
- spec
- spec
- Secret unimonitor-postgres-secret
- volumeClaimTemplates
- extended.py
- TestMonitoringJourney
- controls
- build
- strategy
- spec
- test_control_library.py
- controls
- controls
- controls
- controls
- pytest
- dispatch_finding_alert
- DocxReportGenerator
- get_settings
- unimonitor
- TestIndividualCollectors
- useApi.ts
- Tenant
- Base
- test_control_loader.py
- SecurityDashboard.tsx
- pathlib
- compute_framework_coverage
- generate_report_task
- FakeGraph
- TestRunAsyncHelper
- session.py
- test_every_control_evaluates
- 001_initial_schema.py
- set_sqlite_pragma

## God Nodes (most connected - your core abstractions)
1. `GraphClient` - 103 edges
2. `get_current_user()` - 58 edges
3. `get_settings()` - 52 edges
4. `FindingRepository` - 43 edges
5. `_run()` - 39 edges
6. `Tenant` - 38 edges
7. `AssessmentRepository` - 36 edges
8. `SecretMetadata` - 36 edges
9. `LocalVaultProvider` - 36 edges
10. `require_role()` - 36 edges

## Surprising Connections (you probably didn't know these)
- `TestDocxGenerator` --uses--> `DocxReportGenerator`  [INFERRED]
  tests/unit/test_reporting.py → unimonitor/reporting/docx_generator.py
- `TestAWSSecretsManagerProvider` --uses--> `AWSSecretsManagerProvider`  [INFERRED]
  tests/unit/test_secrets_backends.py → unimonitor/secrets/aws_secrets_manager.py
- `TestDashboardViews` --uses--> `AuditLog`  [INFERRED]
  tests/integration/test_dashboard_views.py → unimonitor/db/models/audit_log.py
- `TestAcquireTokenForClient` --uses--> `AuthenticationError`  [INFERRED]
  tests/unit/test_auth_and_cli.py → unimonitor/exceptions.py
- `TestExchangeCodeForToken` --uses--> `AuthenticationError`  [INFERRED]
  tests/unit/test_auth_and_cli.py → unimonitor/exceptions.py

## Import Cycles
- None detected.

## Communities (201 total, 58 thin omitted)

### Community 0 - "asyncio"
Cohesion: 0.09
Nodes (19): _make_gc(), _run(), TestCollectAll, TestRunCollector, TestSafeGet, _run(), _collect_aws(), _collect_azure_security() (+11 more)

### Community 1 - ".get"
Cohesion: 0.08
Nodes (21): TestGraphResponse, _fail(), _make_client(), _ok(), _run(), TestEntraIdCollector, _get(), _get() (+13 more)

### Community 2 - "Tenant"
Cohesion: 0.10
Nodes (14): ConnectionTestResponse, create_tenant(), delete_tenant(), get_tenant(), list_tenants(), PaginatedTenants, tenant_health(), TenantCreate (+6 more)

### Community 3 - "typing"
Cohesion: 0.13
Nodes (3): Finding, FindingEvidence, FindingHistory

### Community 4 - "AIRemediationEngine"
Cohesion: 0.08
Nodes (10): _run(), TestAIRemediationEngineFallback, TestAIRemediationEngineOpenAI, TestModuleLevelGenerateRemediation, TestNormalise, TestRuleBasedRemediation, AIRemediationEngine, generate_remediation() (+2 more)

### Community 5 - "dashboard.py"
Cohesion: 0.08
Nodes (48): ActivityItem, AuditEntry, AuditViewResponse, _build_framework_coverage(), CategoryBreakdown, CisoDashboardResponse, CisoRiskItem, CloudAggregateResponse (+40 more)

### Community 6 - "NotificationDispatcher"
Cohesion: 0.18
Nodes (7): _make_dispatcher(), _make_settings_obj(), _run(), TestSendSlackWebhook, TestSendSmtp, TestSendTeamsWebhook, TestSendToChannels

### Community 7 - "AsyncClient"
Cohesion: 0.05
Nodes (6): TestAssessmentsAPI, TestAuthEndpoints, TestDashboardAPI, TestFindingsAPI, TestHealthEndpoint, TestReportsAPI

### Community 8 - "test_core_logging.py"
Cohesion: 0.07
Nodes (15): _run(), TestCacheDelete, TestCacheGet, TestCacheLifecycle, TestCacheSet, TestConfigureLogging, TestCorrelationId, TestGetLogger (+7 more)

### Community 9 - "FindingRepository"
Cohesion: 0.09
Nodes (16): AiRemediationRequest, FindingHistoryItem, FindingResponse, findings_summary(), FindingSummaryResponse, get_finding(), get_finding_history(), list_findings() (+8 more)

### Community 10 - "logging.py"
Cohesion: 0.07
Nodes (15): get_logger(), AzureSecurityCollector, AzureSecurityData, CopilotCollector, CopilotData, DefenderCollector, DefenderData, ExchangeCollector (+7 more)

### Community 11 - "test_providers.py"
Cohesion: 0.19
Nodes (9): test_aliases_resolve(), test_provider_ids_cover_all_clouds(), test_service_maps_to_provider(), test_unknown_service_has_no_provider(), _group_by_provider(), CloudProvider, get_provider(), provider_for_service() (+1 more)

### Community 12 - "annotations"
Cohesion: 0.05
Nodes (43): nginx.ingress.kubernetes.io/limit-rps, nginx.ingress.kubernetes.io/proxy-body-size, nginx.ingress.kubernetes.io/proxy-read-timeout, nginx.ingress.kubernetes.io/proxy-send-timeout, nginx.ingress.kubernetes.io/ssl-redirect, Ingress unimonitor, HorizontalPodAutoscaler unimonitor-api, HorizontalPodAutoscaler unimonitor-worker (+35 more)

### Community 13 - "test_worker_tasks.py"
Cohesion: 0.10
Nodes (13): _db_result(), _make_session_factory(), TestCleanupOldRuns, TestGenerateReportTask, TestRunAssessmentTask, TestRunScheduledAssessments, TestRunSingleCollectorTask, TestSendWeeklyDigests (+5 more)

### Community 14 - "package.json"
Cohesion: 0.07
Nodes (39): dependencies, axios@^1.6.5, clsx@^2.1.0, date-fns@^4.4.0, react-dom@^18.2.0, react-is@^19.3.1, react-router-dom@^6.21.3, @tanstack/react-query@^5.17.0 (+31 more)

### Community 15 - "setup_wizard.py"
Cohesion: 0.09
Nodes (8): _ask(), _confirm(), _print(), run_wizard(), setup_aws_secrets_manager(), setup_azure_key_vault(), setup_local_vault(), AWSSecretsManagerProvider

### Community 16 - "security.py"
Cohesion: 0.10
Nodes (8): TestConstantTimeCompare, TestEncryptDecrypt, TestGenerateApiKey, constant_time_compare(), decrypt_secret(), encrypt_secret(), generate_api_key(), _get_fernet()

### Community 17 - "_make_engine"
Cohesion: 0.14
Nodes (9): _make_control_def(), _make_engine(), _make_run(), _run(), TestAssessmentEngineRun, TestEvaluateControl, FindingSeverity, FindingState (+1 more)

### Community 18 - "test_auth_and_cli.py"
Cohesion: 0.14
Nodes (13): TestCreateAccessToken, TestCreateRefreshToken, TestDecodeToken, TestValidateAccessToken, TestValidateRefreshToken, create_access_token(), create_refresh_token(), decode_refresh_token() (+5 more)

### Community 19 - "conftest.py"
Cohesion: 0.13
Nodes (9): admin_user(), auth_headers(), auth_token(), client(), db_session(), engine(), event_loop(), _session_factory() (+1 more)

### Community 20 - "grc.py"
Cohesion: 0.12
Nodes (17): control_crosswalk(), CrosswalkEntry, EvidenceResponse, EvidenceUploadResponse, framework_controls(), framework_coverage(), FrameworkCoverage, gap_analysis() (+9 more)

### Community 21 - "data"
Cohesion: 0.07
Nodes (31): apiVersion, data, kind, metadata, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CONTROLS_DIR, CORS_ORIGINS (+23 more)

### Community 22 - "test_api_auth.py"
Cohesion: 0.14
Nodes (15): test_callback_error_param(), test_callback_invalid_state(), test_entra_login_redirects(), test_get_me_authenticated(), test_get_me_bad_token(), test_get_me_unauthenticated(), test_login_inactive_user(), test_login_success() (+7 more)

### Community 23 - "AssessmentRun"
Cohesion: 0.09
Nodes (18): _assessment_to_response(), AssessmentCreate, AssessmentResponse, AssessmentUpdate, cancel_run(), create_assessment(), delete_assessment(), get_assessment() (+10 more)

### Community 24 - "GraphClient"
Cohesion: 0.07
Nodes (16): TestBatchGet, _test(), TestEnsureToken, _test(), _test(), _test(), TestGetAllPages, _test() (+8 more)

### Community 25 - "SecretMetadata"
Cohesion: 0.12
Nodes (4): _stub_azure_modules(), TestRotationManager, SecretMetadata, RotationManager

### Community 26 - "reports.py"
Cohesion: 0.15
Nodes (11): delete_report(), download_report(), generate_report(), get_report_status(), list_report_runs(), list_reports(), PaginatedRunReports, ReportGenerateRequest (+3 more)

### Community 27 - "controls"
Cohesion: 0.09
Nodes (21): cis_controls_v8, cis_m365_benchmark, gdpr, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+13 more)

### Community 28 - "Tenant"
Cohesion: 0.21
Nodes (6): TestSendDailyDigests, _run_async(), send_daily_digests(), _run(), send_weekly_digests(), _run()

### Community 29 - "_run"
Cohesion: 0.23
Nodes (7): _make_provider(), _make_resolver(), _run(), TestHealthAndStats, TestResolveRef, TestSecretResolverGet, TestSecretResolverWrite

### Community 30 - "ControlLoader"
Cohesion: 0.16
Nodes (3): TestGRCJourney, TestControlLoader, ControlLoader

### Community 31 - "FrameworkCrosswalk"
Cohesion: 0.18
Nodes (3): _make_ctrl(), TestFrameworkCrosswalk, FrameworkCrosswalk

### Community 32 - "LocalVaultProvider"
Cohesion: 0.09
Nodes (5): TestLocalVault, TestProviderProtocolCompliance, TestSecretResolver, LocalVaultProvider, SecretResolver

### Community 33 - "CloudDashboard.tsx"
Cohesion: 0.22
Nodes (9): recharts@^3.10.1, cardStyle, CloudDashboard(), CloudsResponse, FindingCounts, ProviderSummary, scoreColor(), StateCounts (+1 more)

### Community 34 - "auth.py"
Cohesion: 0.09
Nodes (10): get_me(), login(), login_local(), logout(), oauth_callback(), refresh_token(), RefreshRequest, TokenResponse (+2 more)

### Community 35 - "_run"
Cohesion: 0.11
Nodes (8): _run(), _test(), _test(), _test(), _test(), _test(), TestRateLimiter, RateLimiter

### Community 36 - "AssessmentRun"
Cohesion: 0.15
Nodes (6): Assessment, AssessmentRun, AssessmentStatus, AssessmentRunRepository, run_scheduled_assessments(), _run()

### Community 37 - "main.py"
Cohesion: 0.10
Nodes (4): init_db(), create_app(), lifespan(), _setup_otel()

### Community 38 - "App.tsx"
Cohesion: 0.19
Nodes (15): zustand@^5.1.0, App(), ProtectedRoute(), RouteErrorBoundary(), Layout(), NAV_ITEMS, LoginPage(), AuthState (+7 more)

### Community 39 - "cli.py"
Cohesion: 0.14
Nodes (10): run_setup(), main(), run_smoke_tests(), migrate(), secrets_get(), secrets_health(), secrets_set(), setup() (+2 more)

### Community 40 - "controls"
Cohesion: 0.09
Nodes (22): cis_controls_v8, cis_m365_benchmark, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+14 more)

### Community 41 - "controls"
Cohesion: 0.09
Nodes (22): cis_controls_v8, cis_m365_benchmark, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+14 more)

### Community 42 - "controls"
Cohesion: 0.09
Nodes (22): cis_controls_v8, cis_m365_benchmark, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+14 more)

### Community 43 - "controls"
Cohesion: 0.09
Nodes (22): cis_controls_v8, cis_m365_benchmark, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+14 more)

### Community 44 - "controls"
Cohesion: 0.09
Nodes (22): cis_controls_v8, cis_m365_benchmark, gdpr, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+14 more)

### Community 45 - "core/cache.py"
Cohesion: 0.13
Nodes (9): TestCacheKeyHelpers, cache_delete(), cache_delete_pattern(), cache_get(), close_cache(), get_redis(), make_assessment_cache_key(), make_dashboard_cache_key() (+1 more)

### Community 46 - "AzureKeyVaultProvider"
Cohesion: 0.10
Nodes (3): TestBuildProvider, AzureKeyVaultProvider, _build_provider()

### Community 47 - "get_current_user"
Cohesion: 0.19
Nodes (9): ComplianceMapping, ControlResponse, FrameworkControlSummary, FrameworkResponse, get_control(), get_framework(), list_controls(), list_frameworks() (+1 more)

### Community 48 - "get_secret_resolver"
Cohesion: 0.16
Nodes (8): TestGetSecretResolver, _get(), _check(), secrets_rotate(), _rotate(), _set(), get_secret_resolver(), reset_resolver()

### Community 49 - "controls"
Cohesion: 0.09
Nodes (21): cis_controls_v8, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4, soc2 (+13 more)

### Community 50 - "controls"
Cohesion: 0.09
Nodes (21): cis_controls_v8, gdpr, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4, soc2 (+13 more)

### Community 51 - "controls"
Cohesion: 0.09
Nodes (21): cis_controls_v8, cis_m365_benchmark, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+13 more)

### Community 52 - "monitoring.py"
Cohesion: 0.18
Nodes (8): CollectionHistoryEntry, CollectorRunResponse, CollectorStatus, get_collection_history(), get_collectors(), get_platform_health(), PlatformHealthResponse, run_collector()

### Community 53 - "v1/notifications.py"
Cohesion: 0.17
Nodes (14): AlertThresholds, get_notification_settings(), _get_tenant(), _mask(), NotificationSettings, NotificationSettingsUpdate, SlackSettings, SmtpSettings (+6 more)

### Community 54 - "crosswalk.py"
Cohesion: 0.14
Nodes (6): TestCrosswalkFunctions, _build_index(), controls_for_framework(), crosswalk_for_control(), gap_analysis(), get_crosswalk_index()

### Community 55 - "SecretCache"
Cohesion: 0.08
Nodes (3): TestSecretCache, _CacheEntry, SecretCache

### Community 56 - "compliance_mapping"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+11 more)

### Community 57 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+11 more)

### Community 58 - "main"
Cohesion: 0.14
Nodes (5): TestCliMigrate, TestCliSecrets, TestCliStart, main(), secrets()

### Community 59 - "_run"
Cohesion: 0.14
Nodes (3): _run(), TestAWSSecretsManagerProvider, TestAzureKeyVaultProvider

### Community 61 - "controls"
Cohesion: 0.11
Nodes (18): cis_m365_benchmark, hipaa, iso27001_2022, nist_csf_2, soc2, zero_trust, controls, category (+10 more)

### Community 62 - "BaseRepository"
Cohesion: 0.15
Nodes (4): BaseRepository, UserRepository, FrameworkNotFoundError, NotFoundError

### Community 63 - "_parse_legacy_format"
Cohesion: 0.29
Nodes (3): TestParseLegacyFormat, _load_yaml_file(), _parse_legacy_format()

### Community 65 - "controls"
Cohesion: 0.10
Nodes (20): cis_controls_v8, gdpr, iso27001_2022, iso42001, nist_800_53_r5, nist_csf_2, soc2, zero_trust (+12 more)

### Community 66 - "get_settings"
Cohesion: 0.08
Nodes (14): _run(), TestAcquireTokenForClient, TestExchangeCodeForToken, TestGetAuthCodeUrl, TestGetEntraUserInfo, TestGetMsalApp, TestGetMsalAppForTenant, acquire_token_for_client() (+6 more)

### Community 67 - "controls"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, zero_trust, controls (+11 more)

### Community 68 - "compute_score"
Cohesion: 0.14
Nodes (3): TestFindingScoring, compute_framework_score(), compute_score()

### Community 69 - "test_extended_collectors.py"
Cohesion: 0.10
Nodes (18): evaluate(), _new_control_ids(), test_all_new_controls_return_canonical_states(), test_application_inventory_controls_evaluate(), test_cloud_apps_controls_evaluate(), test_copilot_studio_controls_evaluate(), test_defender_identity_controls_evaluate(), test_defender_office_controls_evaluate() (+10 more)

### Community 70 - "ports"
Cohesion: 0.16
Nodes (16): Service unimonitor-postgres, app, name, port, protocol, targetPort, app, matchLabels (+8 more)

### Community 72 - "smoke_test.py"
Cohesion: 0.27
Nodes (5): main(), test_authenticated_endpoints(), test_health(), test_login(), test_static_assets()

### Community 73 - "NotificationDispatcher"
Cohesion: 0.16
Nodes (3): _db_result(), TestPublicAPI, NotificationDispatcher

### Community 75 - "@tanstack/react-query"
Cohesion: 0.11
Nodes (17): dashboardApi, queryClient, AuditEntry, AuditPage(), ComplianceDashboard(), FrameworkBar(), FrameworkCoverage, scoreColor() (+9 more)

### Community 76 - "resolver.py"
Cohesion: 0.13
Nodes (4): AggregatedHealthReport, check_all_providers(), HealthStatus, ProviderType

### Community 79 - "engine.py"
Cohesion: 0.16
Nodes (5): _make_finding(), TestCalculateFrameworkCoverage, TestCalculateScores, calculate_framework_coverage(), calculate_scores()

### Community 80 - "@playwright/test"
Cohesion: 0.28
Nodes (4): loginAsAdmin(), loginViaApi(), TEST_ADMIN, @playwright/test

### Community 83 - "require_role"
Cohesion: 0.13
Nodes (9): get_current_active_user(), require_admin(), require_analyst(), require_compliance(), require_role(), _check(), db_session_context(), get_async_session() (+1 more)

### Community 84 - "controls"
Cohesion: 0.17
Nodes (11): cis_m365_benchmark, iso27001_2022, nist_csf_2, controls, category, compliance_mapping, evaluate, id (+3 more)

### Community 85 - "controls"
Cohesion: 0.17
Nodes (11): cis_m365_benchmark, iso27001_2022, nist_csf_2, controls, category, compliance_mapping, evaluate, id (+3 more)

### Community 86 - "controls"
Cohesion: 0.17
Nodes (11): cis_m365_benchmark, iso27001_2022, nist_csf_2, controls, category, compliance_mapping, evaluate, id (+3 more)

### Community 87 - "labels"
Cohesion: 0.23
Nodes (12): metadata, PersistentVolumeClaim unimonitor-reports, app, app.kubernetes.io/component, app.kubernetes.io/name, labels, name, namespace (+4 more)

### Community 88 - "dependencies.py"
Cohesion: 0.14
Nodes (15): TestGraphClientGet, cache_set(), AssessmentAlreadyRunningError, AssessmentError, AuthenticationError, ConflictError, DatabaseError, generic_exception_handler() (+7 more)

### Community 89 - "env.py"
Cohesion: 0.22
Nodes (4): do_run_migrations(), run_async_migrations(), run_migrations_offline(), run_migrations_online()

### Community 90 - "containers"
Cohesion: 0.18
Nodes (11): envFrom, image, imagePullPolicy, livenessProbe, name, ports, readinessProbe, resources (+3 more)

### Community 91 - "labels"
Cohesion: 0.31
Nodes (11): app, app.kubernetes.io/component, app.kubernetes.io/name, labels, name, namespace, metadata, metadata (+3 more)

### Community 92 - "containers"
Cohesion: 0.18
Nodes (11): command, envFrom, image, imagePullPolicy, livenessProbe, name, ports, resources (+3 more)

### Community 93 - "ErrorBoundary"
Cohesion: 0.22
Nodes (4): DefaultFallback(), ErrorBoundary, Props, State

### Community 94 - "hooks"
Cohesion: 0.18
Nodes (10): additional_dependencies, args, exclude, files, id, stages, repos, hooks (+2 more)

### Community 96 - "ControlDefinition"
Cohesion: 0.15
Nodes (3): TestControlDefinitionRunEvaluate, ControlDefinition, evaluate_one()

### Community 99 - "services"
Cohesion: 0.20
Nodes (9): networks, unimonitor_net, services, driver, version, volumes, postgres_data, redis_data (+1 more)

### Community 100 - "db"
Cohesion: 0.20
Nodes (10): container_name, environment, image, networks, restart, volumes, POSTGRES_DB, POSTGRES_PASSWORD (+2 more)

### Community 101 - "containers"
Cohesion: 0.20
Nodes (10): env, image, name, ports, resources, volumeMounts, containers, template (+2 more)

### Community 102 - "scripts"
Cohesion: 0.20
Nodes (10): scripts, build, dev, lint, preview, test:e2e, test:e2e:report, test:e2e:smoke (+2 more)

### Community 103 - "setup.py"
Cohesion: 0.22
Nodes (5): check_env(), create_default_admin(), generate_password(), main(), run_migrations()

### Community 106 - "test_reporting.py"
Cohesion: 0.27
Nodes (5): _generator(), TestDocxGenerator, TestPdfProviderSections, TestProviderBreakdown, PdfReportGenerator

### Community 108 - "controls"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, zero_trust, controls (+11 more)

### Community 109 - "beat"
Cohesion: 0.22
Nodes (9): command, container_name, depends_on, env_file, environment, image, networks, restart (+1 more)

### Community 110 - "healthcheck"
Cohesion: 0.50
Nodes (9): healthcheck, interval, retries, start_period, test, timeout, healthcheck, healthcheck (+1 more)

### Community 111 - "unimonitor"
Cohesion: 0.22
Nodes (9): unimonitor, container_name, env_file, environment, image, networks, ports, restart (+1 more)

### Community 112 - "spec"
Cohesion: 0.22
Nodes (9): fsGroup, runAsNonRoot, runAsUser, securityContext, serviceAccountName, volumes, spec, name (+1 more)

### Community 113 - "labels"
Cohesion: 0.22
Nodes (9): apiVersion, kind, metadata, Deployment unimonitor-worker, app, app.kubernetes.io/component, app.kubernetes.io/name, labels (+1 more)

### Community 114 - "spec"
Cohesion: 0.22
Nodes (9): fsGroup, runAsNonRoot, runAsUser, securityContext, serviceAccountName, volumes, spec, name (+1 more)

### Community 115 - "controls"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, zero_trust, controls (+11 more)

### Community 116 - "AsyncClient"
Cohesion: 0.15
Nodes (4): TestCisoDashboard, TestCloudAggregate, TestCloudProviderDetail, TestFrameworkCoverage

### Community 117 - "worker"
Cohesion: 0.25
Nodes (8): worker, container_name, env_file, environment, image, networks, restart, volumes

### Community 118 - "namespace.yaml"
Cohesion: 0.25
Nodes (7): apiVersion, kind, app.kubernetes.io/managed-by, app.kubernetes.io/name, metadata, labels, name

### Community 119 - "PersistentVolumeClaim unimonitor-redis-data"
Cohesion: 0.32
Nodes (8): metadata, metadata, PersistentVolumeClaim unimonitor-redis-data, name, namespace, apiVersion, kind, metadata

### Community 120 - "template"
Cohesion: 0.39
Nodes (8): spec, spec, spec, app, matchLabels, replicas, selector, template

### Community 121 - "AssessmentsPage.tsx"
Cohesion: 0.28
Nodes (8): assessmentsApi, Assessment, AssessmentCard(), AssessmentRun, AssessmentsPage(), FRAMEWORK_LABELS, FRAMEWORK_OPTIONS, RunStatusIcon()

### Community 122 - "ExecutiveDashboard.tsx"
Cohesion: 0.32
Nodes (7): ExecutiveDashboard(), FrameworkCoverage, ScoreGauge(), StatCard(), tooltipStyle, TopRisk, TrendPoint

### Community 123 - "compilerOptions"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 126 - "test_windows_build_assets.py"
Cohesion: 0.19
Nodes (6): _spec_hiddenimports(), test_nsis_does_not_require_third_party_plugins(), test_nsis_icon_exists(), test_release_workflow_builds_installer_on_demand(), test_spec_does_not_reference_removed_secrets_factory(), test_spec_hiddenimports_point_at_real_unimonitor_modules()

### Community 127 - "redis"
Cohesion: 0.29
Nodes (7): command, container_name, image, networks, restart, volumes, redis

### Community 128 - "Deployment unimonitor-api"
Cohesion: 0.29
Nodes (6): apiVersion, kind, Deployment unimonitor-api, ServiceAccount unimonitor, apiVersion, kind

### Community 129 - "spec"
Cohesion: 0.29
Nodes (7): spec, app, matchLabels, replicas, selector, template, metadata

### Community 130 - "service.yaml"
Cohesion: 0.29
Nodes (6): Service unimonitor-api, Service unimonitor-redis, apiVersion, kind, apiVersion, kind

### Community 131 - "Deployment unimonitor-beat"
Cohesion: 0.29
Nodes (6): apiVersion, kind, apiVersion, kind, Deployment unimonitor-beat, Deployment unimonitor-redis

### Community 132 - "test_cloud_providers.py"
Cohesion: 0.11
Nodes (17): aws_data(), _BotoClient, _BotoSession, evaluate(), _FakeHTTP, gcp_data(), gws_data(), _run() (+9 more)

### Community 133 - "CisoDashboard.tsx"
Cohesion: 0.25
Nodes (8): cardStyle, CisoDashboard(), CisoResponse, CisoRiskItem, CloudRiskRow, FrameworkRow, scoreColor(), TrendPoint

### Community 134 - "CloudProviderPage.tsx"
Cohesion: 0.24
Nodes (10): cardStyle, CategoryRow, CloudProviderPage(), CoverageBar(), FindingRow, FrameworkRow, ProviderDetail, ProviderSummary (+2 more)

### Community 135 - "controls"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, zero_trust, controls (+11 more)

### Community 136 - "db"
Cohesion: 0.40
Nodes (6): condition, db, redis, condition, depends_on, depends_on

### Community 137 - "initContainers"
Cohesion: 0.33
Nodes (6): command, envFrom, image, name, securityContext, initContainers

### Community 138 - "spec"
Cohesion: 0.33
Nodes (6): spec, storage, requests, accessModes, resources, storageClassName

### Community 139 - "spec"
Cohesion: 0.33
Nodes (6): StatefulSet unimonitor-postgres, replicas, serviceName, apiVersion, kind, spec

### Community 140 - "Secret unimonitor-postgres-secret"
Cohesion: 0.33
Nodes (6): Secret unimonitor-postgres-secret, apiVersion, kind, stringData, type, password

### Community 141 - "volumeClaimTemplates"
Cohesion: 0.33
Nodes (6): requests, accessModes, resources, volumeClaimTemplates, metadata, spec

### Community 142 - "extended.py"
Cohesion: 0.13
Nodes (15): collected(), _collect_defender(), _collect_purview(), collect_cloud_apps(), collect_copilot_studio(), collect_defender_identity(), collect_defender_office(), collect_ediscovery() (+7 more)

### Community 144 - "controls"
Cohesion: 0.10
Nodes (19): cis_controls_v8, gdpr, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, zero_trust, controls (+11 more)

### Community 145 - "build"
Cohesion: 0.60
Nodes (5): build, context, dockerfile, build, build

### Community 146 - "strategy"
Cohesion: 0.40
Nodes (5): maxSurge, maxUnavailable, strategy, rollingUpdate, type

### Community 147 - "spec"
Cohesion: 0.40
Nodes (5): spec, storage, requests, accessModes, resources

### Community 148 - "test_control_library.py"
Cohesion: 0.16
Nodes (4): controls(), FrameworkMeta, get_framework(), list_frameworks()

### Community 149 - "controls"
Cohesion: 0.12
Nodes (16): cis_controls_v8, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4, soc2, controls (+8 more)

### Community 150 - "controls"
Cohesion: 0.12
Nodes (16): cis_controls_v8, gdpr, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4, soc2, controls (+8 more)

### Community 151 - "controls"
Cohesion: 0.11
Nodes (18): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, controls, category (+10 more)

### Community 152 - "controls"
Cohesion: 0.12
Nodes (15): cis_controls_v8, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4, soc2, controls, category (+7 more)

### Community 154 - "dispatch_finding_alert"
Cohesion: 0.36
Nodes (3): TestDispatchFindingAlert, dispatch_finding_alert(), _run()

### Community 163 - "get_settings"
Cohesion: 0.13
Nodes (6): get_settings(), _aws_snapshot(), collect_aws(), collect_gcp(), collect_google_workspace(), _rest()

### Community 178 - "useApi.ts"
Cohesion: 0.11
Nodes (23): lucide-react@^1.73.0, react@^18.2.0, api, findingsApi, reportsApi, Finding, FindingListResponse, FindingsPage() (+15 more)

### Community 179 - "Tenant"
Cohesion: 0.14
Nodes (4): seed_notification_settings(), NotificationSetting, ReportStatus, Tenant

### Community 181 - "Base"
Cohesion: 0.11
Nodes (10): Base, AuditLog, Control, ControlMapping, Framework, Report, RiskItem, RiskScore (+2 more)

### Community 182 - "test_control_loader.py"
Cohesion: 0.18
Nodes (4): TestLoadAllControls, TestLoadControlsForFrameworks, load_all_controls(), load_controls_for_frameworks()

### Community 183 - "SecurityDashboard.tsx"
Cohesion: 0.43
Nodes (6): monitoringApi, CollectorRow(), CollectorStatus, SecurityDashboard(), ServiceCard, StatusIcon()

## Knowledge Gaps
- **1 isolated node(s):** `unimonitor`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 1489 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **58 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_settings()` connect `get_settings` to `AIRemediationEngine`, `test_core_logging.py`, `security.py`, `test_auth_and_cli.py`, `grc.py`, `GraphClient`, `reports.py`, `auth.py`, `_run`, `main.py`, `core/cache.py`, `Tenant`, `Base`, `Settings`, `get_settings`, `test_extended_collectors.py`, `BaseReportGenerator`, `dependencies.py`, `test_reporting.py`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `GraphClient` (e.g. with `TestBatchGet` and `TestEnsureToken`) actually correct?**
  _`GraphClient` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `unimonitor` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `asyncio` be split into smaller, more focused modules?**
  _Cohesion score 0.08956228956228957 - nodes in this community are weakly interconnected._
- **Why does `ControlLoader` connect `ControlLoader` to `ControlDefinition`, `typing`, `test_cloud_providers.py`, `test_extended_collectors.py`, `dashboard.py`, `logging.py`, `_make_engine`, `test_control_library.py`, `test_control_loader.py`, `compute_framework_coverage`, `FrameworkCrosswalk`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `FindingRepository` (e.g. with `Finding` and `FindingEvidence`) actually correct?**
  _`FindingRepository` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Should `.get` be split into smaller, more focused modules?**
  _Cohesion score 0.07785602503912363 - nodes in this community are weakly interconnected._