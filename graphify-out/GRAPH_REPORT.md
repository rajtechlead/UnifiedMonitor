# Graph Report - cbb7236d17c7b011ebaca937  (2026-11-17)

## Corpus Check
- 214 files · ~114,923 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: (none) 7, .example 2, .ini 2)

## Summary
- 3644 nodes · 7436 edges · 210 communities (146 shown, 64 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 436 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e9a36903`
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
- service.py
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
- .set_secret
- CloudDashboard.tsx
- auth.py
- RateLimiter
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
- _build_provider
- get_current_user
- get_secret_resolver
- controls
- controls
- controls
- monitoring.py
- v1/notifications.py
- CloudError
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
- get_msal_app
- controls
- compute_score
- test_extended_collectors.py
- ports
- CsvReportGenerator
- smoke_test.py
- NotificationDispatcher
- BaseReportGenerator
- useApi.ts
- get_logger
- AsyncClient
- _normalise
- test_crosswalk.py
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
- App
- hooks
- CollectorRegistry
- ControlDefinition
- test_reporting.py
- services
- db
- containers
- scripts
- AssessmentRepository
- TestFindingsJourney
- m365.py
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
- test_e2e_journeys.py
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
- LocalVaultProvider
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
- _make_session_factory
- DocxReportGenerator
- microsoft_complete
- get_settings
- unimonitor
- create_app
- TestIndividualCollectors
- ReportsPage.tsx
- AssessmentEngine
- httpx
- Base
- load_controls_for_frameworks
- verify_bundled_ui.py
- config.py
- compute_framework_coverage
- generate_report_task
- acquire_token_for_client
- SettingsPage.tsx
- session.py
- SecretResolver
- test_reports_api.py
- _graph_mock
- _spa_directory
- .get
- get_audit_logger
- TestCisoDashboard
- load_all_controls
- _BotoClient
- TestPermissions
- platform_catalogue
- _isolated_vault
- _check
- permissions.py

## God Nodes (most connected - your core abstractions)
1. `GraphClient` - 103 edges
2. `get_current_user()` - 58 edges
3. `get_settings()` - 57 edges
4. `FindingRepository` - 43 edges
5. `Tenant` - 39 edges
6. `_run()` - 39 edges
7. `Base` - 36 edges
8. `AssessmentRepository` - 36 edges
9. `SecretMetadata` - 36 edges
10. `get_logger()` - 36 edges

## Surprising Connections (you probably didn't know these)
- `main()` --indirect_call--> `client()`  [INFERRED]
  scripts/smoke_test.py → tests/conftest.py
- `TestDocxGenerator` --uses--> `DocxReportGenerator`  [INFERRED]
  tests/unit/test_reporting.py → unimonitor/reporting/docx_generator.py
- `TestAWSSecretsManagerProvider` --uses--> `AWSSecretsManagerProvider`  [INFERRED]
  tests/unit/test_secrets_backends.py → unimonitor/secrets/aws_secrets_manager.py
- `TestDashboardViews` --uses--> `AuditLog`  [INFERRED]
  tests/integration/test_dashboard_views.py → unimonitor/db/models/audit_log.py
- `TestEvaluateControl` --uses--> `FindingSeverity`  [INFERRED]
  tests/unit/test_grc_engine.py → unimonitor/db/models/finding.py

## Import Cycles
- None detected.

## Communities (210 total, 64 thin omitted)

### Community 0 - "asyncio"
Cohesion: 0.13
Nodes (15): TestSafeGet, _collect_aws(), _collect_azure_security(), _collect_copilot(), _collect_defender(), _collect_entra_id(), _collect_exchange(), _collect_gcp() (+7 more)

### Community 1 - ".get"
Cohesion: 0.09
Nodes (19): _fail(), _make_client(), _ok(), _run(), TestEntraIdCollector, _get(), _get(), _get() (+11 more)

### Community 2 - "Tenant"
Cohesion: 0.09
Nodes (14): ConnectionTestResponse, create_tenant(), delete_tenant(), get_tenant(), list_tenants(), PaginatedTenants, tenant_health(), TenantCreate (+6 more)

### Community 4 - "AIRemediationEngine"
Cohesion: 0.08
Nodes (10): _run(), TestAIRemediationEngineFallback, TestAIRemediationEngineOpenAI, TestModuleLevelGenerateRemediation, TestNormalise, TestRuleBasedRemediation, AIRemediationEngine, generate_remediation() (+2 more)

### Community 5 - "dashboard.py"
Cohesion: 0.08
Nodes (50): ActivityItem, AuditEntry, AuditViewResponse, _build_framework_coverage(), CategoryBreakdown, CisoDashboardResponse, CisoRiskItem, CloudAggregateResponse (+42 more)

### Community 6 - "NotificationDispatcher"
Cohesion: 0.18
Nodes (7): _make_dispatcher(), _make_settings_obj(), _run(), TestSendSlackWebhook, TestSendSmtp, TestSendTeamsWebhook, TestSendToChannels

### Community 7 - "AsyncClient"
Cohesion: 0.05
Nodes (6): TestAssessmentsAPI, TestAuthEndpoints, TestDashboardAPI, TestFindingsAPI, TestHealthEndpoint, TestReportsAPI

### Community 8 - "test_core_logging.py"
Cohesion: 0.07
Nodes (16): _run(), TestCacheDelete, TestCacheGet, TestCacheKeyHelpers, TestCacheLifecycle, TestCacheSet, TestConfigureLogging, TestCorrelationId (+8 more)

### Community 9 - "FindingRepository"
Cohesion: 0.08
Nodes (16): AiRemediationRequest, FindingHistoryItem, FindingResponse, findings_summary(), FindingSummaryResponse, get_finding(), get_finding_history(), list_findings() (+8 more)

### Community 10 - "logging.py"
Cohesion: 0.07
Nodes (14): AzureSecurityCollector, AzureSecurityData, CopilotCollector, CopilotData, DefenderCollector, DefenderData, ExchangeCollector, ExchangeData (+6 more)

### Community 11 - "test_providers.py"
Cohesion: 0.20
Nodes (8): test_aliases_resolve(), test_provider_ids_cover_all_clouds(), test_service_maps_to_provider(), test_unknown_service_has_no_provider(), CloudProvider, get_provider(), provider_for_service(), provider_ids()

### Community 12 - "annotations"
Cohesion: 0.05
Nodes (43): nginx.ingress.kubernetes.io/limit-rps, nginx.ingress.kubernetes.io/proxy-body-size, nginx.ingress.kubernetes.io/proxy-read-timeout, nginx.ingress.kubernetes.io/proxy-send-timeout, nginx.ingress.kubernetes.io/ssl-redirect, Ingress unimonitor, HorizontalPodAutoscaler unimonitor-api, HorizontalPodAutoscaler unimonitor-worker (+35 more)

### Community 13 - "test_worker_tasks.py"
Cohesion: 0.11
Nodes (9): TestRunAssessmentTask, TestRunAsyncHelper, TestRunScheduledAssessments, TestRunSingleCollectorTask, run_assessment_task(), _run(), _run_async(), run_scheduled_assessments() (+1 more)

### Community 14 - "package.json"
Cohesion: 0.07
Nodes (39): dependencies, axios@^1.6.5, clsx@^2.1.0, date-fns@^4.4.0, lucide-react@^1.73.0, react@^18.2.0, react-is@^19.3.1, react-router-dom@^6.21.3 (+31 more)

### Community 15 - "service.py"
Cohesion: 0.14
Nodes (18): create_admin(), db_session_context(), CloudConnection, aws_credentials_for(), connect_microsoft(), connect_platform(), connection_dict(), create_first_admin() (+10 more)

### Community 16 - "security.py"
Cohesion: 0.10
Nodes (8): TestConstantTimeCompare, TestEncryptDecrypt, TestGenerateApiKey, constant_time_compare(), decrypt_secret(), encrypt_secret(), generate_api_key(), _get_fernet()

### Community 17 - "_make_engine"
Cohesion: 0.19
Nodes (6): _make_control_def(), _make_engine(), _make_run(), _run(), TestAssessmentEngineRun, TestEvaluateControl

### Community 18 - "test_auth_and_cli.py"
Cohesion: 0.13
Nodes (11): TestCreateAccessToken, TestCreateRefreshToken, TestDecodeToken, TestValidateAccessToken, TestValidateRefreshToken, create_access_token(), decode_refresh_token(), decode_token() (+3 more)

### Community 19 - "conftest.py"
Cohesion: 0.13
Nodes (9): admin_user(), auth_headers(), auth_token(), client(), db_session(), engine(), event_loop(), _session_factory() (+1 more)

### Community 20 - "grc.py"
Cohesion: 0.10
Nodes (17): control_crosswalk(), CrosswalkEntry, EvidenceResponse, EvidenceUploadResponse, framework_controls(), framework_coverage(), FrameworkCoverage, gap_analysis() (+9 more)

### Community 21 - "data"
Cohesion: 0.07
Nodes (31): apiVersion, data, kind, metadata, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CONTROLS_DIR, CORS_ORIGINS (+23 more)

### Community 22 - "test_api_auth.py"
Cohesion: 0.14
Nodes (15): test_callback_error_param(), test_callback_invalid_state(), test_entra_login_redirects(), test_get_me_authenticated(), test_get_me_bad_token(), test_get_me_unauthenticated(), test_login_inactive_user(), test_login_success() (+7 more)

### Community 23 - "AssessmentRun"
Cohesion: 0.17
Nodes (14): _assessment_to_response(), AssessmentCreate, AssessmentResponse, AssessmentUpdate, create_assessment(), get_assessment(), get_run(), list_assessments() (+6 more)

### Community 24 - "GraphClient"
Cohesion: 0.06
Nodes (29): _run(), TestBatchGet, _test(), TestEnsureToken, _test(), _test(), _test(), TestGetAllPages (+21 more)

### Community 25 - "SecretMetadata"
Cohesion: 0.08
Nodes (4): _stub_azure_modules(), TestRotationManager, SecretMetadata, RotationManager

### Community 26 - "reports.py"
Cohesion: 0.12
Nodes (12): delete_report(), download_report(), generate_report(), get_report_status(), list_report_runs(), list_reports(), PaginatedRunReports, ReportGenerateRequest (+4 more)

### Community 27 - "controls"
Cohesion: 0.09
Nodes (21): cis_controls_v8, cis_m365_benchmark, gdpr, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+13 more)

### Community 28 - "Tenant"
Cohesion: 0.22
Nodes (6): TestSendWeeklyDigests, _run_async(), send_daily_digests(), _run(), send_weekly_digests(), _run()

### Community 29 - "_run"
Cohesion: 0.23
Nodes (7): _make_provider(), _make_resolver(), _run(), TestHealthAndStats, TestResolveRef, TestSecretResolverGet, TestSecretResolverWrite

### Community 30 - "ControlLoader"
Cohesion: 0.16
Nodes (3): TestGRCJourney, TestControlLoader, ControlLoader

### Community 31 - "FrameworkCrosswalk"
Cohesion: 0.21
Nodes (3): _make_ctrl(), TestFrameworkCrosswalk, FrameworkCrosswalk

### Community 33 - "CloudDashboard.tsx"
Cohesion: 0.17
Nodes (13): recharts@^3.10.1, cardStyle, CloudDashboard(), CloudsResponse, FindingCounts, ProviderSummary, scoreColor(), StateCounts (+5 more)

### Community 34 - "auth.py"
Cohesion: 0.08
Nodes (11): get_me(), login_local(), logout(), refresh_token(), RefreshRequest, TokenResponse, UserProfile, get_current_active_user() (+3 more)

### Community 36 - "AssessmentRun"
Cohesion: 0.17
Nodes (3): AssessmentRun, AssessmentRunRepository, _run()

### Community 38 - "App.tsx"
Cohesion: 0.13
Nodes (22): zustand@^5.1.0, ProtectedRoute(), Layout(), NAV_ITEMS, api, LoginPage(), card, input (+14 more)

### Community 39 - "cli.py"
Cohesion: 0.20
Nodes (6): migrate(), secrets_health(), setup(), smoke_test(), start(), init_db()

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
Cohesion: 0.10
Nodes (10): login(), oauth_callback(), get_entra_user_info(), cache_delete(), cache_delete_pattern(), cache_get(), cache_set(), close_cache() (+2 more)

### Community 47 - "get_current_user"
Cohesion: 0.20
Nodes (9): ComplianceMapping, ControlResponse, FrameworkControlSummary, FrameworkResponse, get_control(), get_framework(), list_controls(), list_frameworks() (+1 more)

### Community 48 - "get_secret_resolver"
Cohesion: 0.13
Nodes (10): TestGetSecretResolver, secrets_get(), _get(), _check(), secrets_rotate(), _rotate(), secrets_set(), _set() (+2 more)

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

### Community 54 - "CloudError"
Cohesion: 0.14
Nodes (11): _bootstrap(), TestConnectPlatforms, fake_validate(), fake_aws(), fake_validate(), fake_start(), TestFirstRunWindow, CloudError (+3 more)

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

### Community 65 - "controls"
Cohesion: 0.10
Nodes (20): cis_controls_v8, gdpr, iso27001_2022, iso42001, nist_800_53_r5, nist_csf_2, soc2, zero_trust (+12 more)

### Community 66 - "get_msal_app"
Cohesion: 0.13
Nodes (7): TestGetAuthCodeUrl, TestGetMsalApp, TestGetMsalAppForTenant, build_authorize_url(), get_auth_code_url(), get_msal_app(), get_msal_app_for_tenant()

### Community 67 - "controls"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, zero_trust, controls (+11 more)

### Community 68 - "compute_score"
Cohesion: 0.14
Nodes (3): TestFindingScoring, compute_framework_score(), compute_score()

### Community 69 - "test_extended_collectors.py"
Cohesion: 0.08
Nodes (20): evaluate(), FakeGraph, _new_control_ids(), _run(), test_all_new_controls_return_canonical_states(), test_application_inventory_controls_evaluate(), test_cloud_apps_controls_evaluate(), test_copilot_studio_controls_evaluate() (+12 more)

### Community 70 - "ports"
Cohesion: 0.16
Nodes (16): Service unimonitor-postgres, app, name, port, protocol, targetPort, app, matchLabels (+8 more)

### Community 72 - "smoke_test.py"
Cohesion: 0.23
Nodes (6): main(), run_smoke_tests(), test_authenticated_endpoints(), test_health(), test_login(), test_static_assets()

### Community 73 - "NotificationDispatcher"
Cohesion: 0.16
Nodes (3): _db_result(), TestPublicAPI, NotificationDispatcher

### Community 75 - "useApi.ts"
Cohesion: 0.11
Nodes (22): dashboardApi, findingsApi, monitoringApi, AuditEntry, Finding, FindingListResponse, FindingsPage(), SEVERITIES (+14 more)

### Community 76 - "get_logger"
Cohesion: 0.07
Nodes (7): get_logger(), AWSSecretsManagerProvider, AzureKeyVaultProvider, AggregatedHealthReport, check_all_providers(), HealthStatus, ProviderType

### Community 77 - "AsyncClient"
Cohesion: 0.08
Nodes (3): TestAssessmentJourney, TestDashboardJourney, TestLoginJourney

### Community 79 - "test_crosswalk.py"
Cohesion: 0.07
Nodes (13): _make_finding(), TestCalculateFrameworkCoverage, TestCalculateScores, TestCrosswalkFunctions, FindingSeverity, FindingState, _build_index(), controls_for_framework() (+5 more)

### Community 80 - "@playwright/test"
Cohesion: 0.28
Nodes (4): loginAsAdmin(), loginViaApi(), TEST_ADMIN, @playwright/test

### Community 83 - "require_role"
Cohesion: 0.33
Nodes (4): require_admin(), require_analyst(), require_compliance(), require_role()

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
Cohesion: 0.18
Nodes (11): AssessmentAlreadyRunningError, AssessmentError, AuthorisationError, ConflictError, DatabaseError, FrameworkNotFoundError, generic_exception_handler(), NotFoundError (+3 more)

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

### Community 93 - "App"
Cohesion: 0.14
Nodes (9): react-dom@^18.2.0, App(), RouteErrorBoundary(), SetupGate(), ErrorBoundary, queryClient, AuditPage(), SocDashboard() (+1 more)

### Community 94 - "hooks"
Cohesion: 0.18
Nodes (10): additional_dependencies, args, exclude, files, id, stages, repos, hooks (+2 more)

### Community 95 - "CollectorRegistry"
Cohesion: 0.13
Nodes (7): _make_gc(), _run(), TestCollectAll, TestRunCollector, CollectorRegistry, evaluate_one(), _run()

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

### Community 103 - "AssessmentRepository"
Cohesion: 0.13
Nodes (5): cancel_run(), delete_assessment(), trigger_run(), Assessment, AssessmentRepository

### Community 105 - "m365.py"
Cohesion: 0.19
Nodes (10): _client(), _graph(), M365Error, poll_device_flow(), provision_app(), ProvisionResult, _resolve_role_ids(), start_device_flow() (+2 more)

### Community 106 - "test_reporting.py"
Cohesion: 0.19
Nodes (6): _generator(), _pdf_text(), TestDocxGenerator, TestPdfProviderSections, TestProviderBreakdown, PdfReportGenerator

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
Cohesion: 0.19
Nodes (3): TestCloudAggregate, TestCloudProviderDetail, TestFrameworkCoverage

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
Cohesion: 0.16
Nodes (11): DefaultFallback(), Props, State, ExecutiveDashboard(), FrameworkCoverage, ScoreGauge(), StatCard(), tooltipStyle (+3 more)

### Community 123 - "compilerOptions"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 126 - "test_windows_build_assets.py"
Cohesion: 0.11
Nodes (10): _spec_hiddenimports(), test_docker_images_copy_the_package_before_installing(), test_nsis_does_not_require_third_party_plugins(), test_nsis_icon_exists(), test_nsis_is_put_on_path_before_it_is_used(), test_release_workflow_builds_installer_on_demand(), test_spec_does_not_reference_removed_secrets_factory(), test_spec_hiddenimports_point_at_real_unimonitor_modules() (+2 more)

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
Cohesion: 0.14
Nodes (15): aws_data(), evaluate(), _FakeHTTP, gcp_data(), gws_data(), _run(), test_aws_controls_detect_failure(), test_aws_controls_evaluate() (+7 more)

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
Cohesion: 0.15
Nodes (13): collected(), collect_cloud_apps(), collect_copilot_studio(), collect_defender_identity(), collect_defender_office(), collect_ediscovery(), collect_insider_risk(), collect_intune_extended() (+5 more)

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
Cohesion: 0.13
Nodes (5): controls(), test_every_control_evaluates(), FrameworkMeta, get_framework(), list_frameworks()

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

### Community 154 - "_make_session_factory"
Cohesion: 0.13
Nodes (9): _db_result(), _make_session_factory(), TestCleanupOldRuns, TestDispatchFindingAlert, TestGenerateReportTask, TestSendDailyDigests, cleanup_old_runs(), dispatch_finding_alert() (+1 more)

### Community 157 - "microsoft_complete"
Cohesion: 0.11
Nodes (8): CompleteRequest, connect(), FirstAdmin, microsoft_complete(), microsoft_device_code(), remove_connection(), require_setup_admin(), setup_status()

### Community 163 - "get_settings"
Cohesion: 0.20
Nodes (7): get_settings(), _aws_snapshot(), collect_aws(), collect_gcp(), collect_google_workspace(), _google_token_from_store(), _rest()

### Community 176 - "create_app"
Cohesion: 0.15
Nodes (3): _build_spa(), TestSpaServing, create_app()

### Community 178 - "ReportsPage.tsx"
Cohesion: 0.29
Nodes (7): reportsApi, FORMAT_LABELS, FORMAT_OPTIONS, Report, ReportsPage(), RunReportSummary, StatusIcon()

### Community 180 - "httpx"
Cohesion: 0.09
Nodes (10): _rsa_key(), TestGoogleServiceAccounts, _google_token(), validate_gcp(), validate_workspace(), _CachedToken, GoogleAuthError, mint_access_token() (+2 more)

### Community 181 - "Base"
Cohesion: 0.09
Nodes (14): upgrade(), Base, set_sqlite_pragma(), AuditLog, Control, ControlMapping, Framework, FindingEvidence (+6 more)

### Community 183 - "verify_bundled_ui.py"
Cohesion: 0.16
Nodes (4): check(), fetch(), free_port(), main()

### Community 184 - "config.py"
Cohesion: 0.12
Nodes (3): draw_icon(), main(), _load_or_create_secret_key()

### Community 188 - "generate_report_task"
Cohesion: 0.22
Nodes (3): ReportStatus, generate_report_task(), _run_async()

### Community 189 - "acquire_token_for_client"
Cohesion: 0.18
Nodes (7): _run(), TestAcquireTokenForClient, TestExchangeCodeForToken, TestGetEntraUserInfo, acquire_token_for_client(), exchange_code_for_token(), _exchange_code_for_token_sync()

### Community 190 - "SettingsPage.tsx"
Cohesion: 0.23
Nodes (13): Connection, DeviceCode, Field(), inputStyle, Platform, PlatformConnector(), PlatformField, FormField() (+5 more)

### Community 191 - "session.py"
Cohesion: 0.25
Nodes (3): create_all_tables(), drop_all_tables(), get_async_session()

### Community 194 - "_graph_mock"
Cohesion: 0.25
Nodes (3): _graph_mock(), handler(), TestMicrosoftSetup

### Community 197 - "get_audit_logger"
Cohesion: 0.29
Nodes (3): TestGetLogger, get_audit_logger(), log_audit_event()

### Community 199 - "load_all_controls"
Cohesion: 0.33
Nodes (3): TestLoadAllControls, load_all_controls(), _load_yaml_file()

## Knowledge Gaps
- **1 isolated node(s):** `unimonitor`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 1565 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **64 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_settings()` connect `get_settings` to `AIRemediationEngine`, `test_core_logging.py`, `logging.py`, `service.py`, `security.py`, `test_auth_and_cli.py`, `grc.py`, `reports.py`, `auth.py`, `RateLimiter`, `main.py`, `core/cache.py`, `create_app`, `AssessmentEngine`, `Base`, `config.py`, `acquire_token_for_client`, `Settings`, `get_msal_app`, `test_extended_collectors.py`, `BaseReportGenerator`, `test_reporting.py`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `GraphClient` (e.g. with `TestBatchGet` and `TestEnsureToken`) actually correct?**
  _`GraphClient` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `unimonitor` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `asyncio` be split into smaller, more focused modules?**
  _Cohesion score 0.12692307692307692 - nodes in this community are weakly interconnected._
- **Why does `AssessmentRun` connect `AssessmentRun` to `test_reports_api.py`, `typing`, `AssessmentRepository`, `_make_session_factory`, `NotificationDispatcher`, `test_worker_tasks.py`, `AssessmentEngine`, `monitoring.py`, `Base`, `AssessmentRun`, `config.py`, `reports.py`, `generate_report_task`, `CollectorRegistry`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Should `.get` be split into smaller, more focused modules?**
  _Cohesion score 0.08548168249660787 - nodes in this community are weakly interconnected._
- **Why does `get_current_user()` connect `grc.py` to `auth.py`, `Tenant`, `dashboard.py`, `FindingRepository`, `get_current_user`, `monitoring.py`, `v1/notifications.py`, `AssessmentRun`, `GraphClient`, `reports.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._