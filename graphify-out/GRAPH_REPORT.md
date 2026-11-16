# Graph Report - cbb7236d17c7b011ebaca937  (2026-11-16)

## Corpus Check
- 183 files · ~90,849 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: (none) 7, .example 2, .ini 2)

## Summary
- 3112 nodes · 6299 edges · 187 communities (121 shown, 66 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 456 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1d2b624d`
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
- .run
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
- LocalVaultProvider
- _run
- ControlLoader
- FrameworkCrosswalk
- SecretResolver
- v1/notifications.py
- auth.py
- RateLimiter
- generate_report_task
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
- @tanstack/react-query
- crosswalk.py
- SecretCache
- compliance_mapping
- compilerOptions
- main
- _run
- structlog
- controls
- BaseRepository
- test_control_loader.py
- config.py
- controls
- get_settings
- controls
- compute_score
- acquire_token_for_client
- ports
- CsvReportGenerator
- smoke_test.py
- TestAzureKeyVaultProvider
- BaseReportGenerator
- useApi.ts
- client.py
- TestLoginJourney
- _normalise
- engine.py
- @playwright/test
- SecretProvider
- ExcelReportGenerator
- session.py
- controls
- controls
- controls
- labels
- require_role
- env.py
- containers
- labels
- containers
- ErrorBoundary
- hooks
- AsyncClient
- ControlDefinition
- test_reporting.py
- ._get_output_path
- services
- db
- containers
- scripts
- setup.py
- TestFindingsJourney
- TestDashboardJourney
- _parse_legacy_format
- _parse_list_format
- controls
- beat
- healthcheck
- unimonitor
- spec
- labels
- spec
- controls
- .get
- worker
- namespace.yaml
- PersistentVolumeClaim unimonitor-redis-data
- template
- AssessmentsPage.tsx
- ExecutiveDashboard.tsx
- compilerOptions
- TestReportsJourney
- TestTenantJourney
- redis
- Deployment unimonitor-api
- spec
- service.yaml
- Deployment unimonitor-beat
- ComplianceDashboard.tsx
- SettingsPage.tsx
- controls
- db
- initContainers
- spec
- spec
- Secret unimonitor-postgres-secret
- volumeClaimTemplates
- RiskDashboard.tsx
- TestMonitoringJourney
- controls
- build
- strategy
- spec
- test_control_library.py
- azure_security.py
- copilot.py
- controls
- TestAssessmentEngineRun
- pytest
- test_api_health.py
- unimonitor
- get_audit_logger
- TestFindingsAPI
- TestHealthEndpoint
- AssessmentEngine
- test_secrets_backends.py
- get_entra_user_info

## God Nodes (most connected - your core abstractions)
1. `GraphClient` - 90 edges
2. `get_current_user()` - 55 edges
3. `get_settings()` - 46 edges
4. `FindingRepository` - 42 edges
5. `Tenant` - 41 edges
6. `_run()` - 39 edges
7. `SecretMetadata` - 36 edges
8. `LocalVaultProvider` - 36 edges
9. `require_role()` - 36 edges
10. `AssessmentRun` - 35 edges

## Surprising Connections (you probably didn't know these)
- `TestBatchGet` --uses--> `GraphResponse`  [INFERRED]
  tests/unit/test_graph_client.py → unimonitor/graph/client.py
- `TestEvaluateControl` --uses--> `FindingSeverity`  [INFERRED]
  tests/unit/test_grc_engine.py → unimonitor/db/models/finding.py
- `TestEvaluateControl` --uses--> `FindingState`  [INFERRED]
  tests/unit/test_grc_engine.py → unimonitor/db/models/finding.py
- `TestAzureKeyVaultProvider` --uses--> `AzureKeyVaultProvider`  [INFERRED]
  tests/unit/test_secrets_backends.py → unimonitor/secrets/azure_keyvault.py
- `TestGraphClientGet` --uses--> `GraphClient`  [INFERRED]
  tests/unit/test_graph_client.py → unimonitor/graph/client.py

## Import Cycles
- None detected.

## Communities (187 total, 66 thin omitted)

### Community 0 - "asyncio"
Cohesion: 0.08
Nodes (19): _make_gc(), _run(), TestCollectAll, TestIndividualCollectors, TestRunCollector, TestSafeGet, _collect_azure_security(), _collect_copilot() (+11 more)

### Community 1 - ".get"
Cohesion: 0.09
Nodes (19): _fail(), _make_client(), _ok(), _run(), TestEntraIdCollector, _get(), _get(), _get() (+11 more)

### Community 2 - "Tenant"
Cohesion: 0.09
Nodes (15): ConnectionTestResponse, create_tenant(), delete_tenant(), get_tenant(), list_tenants(), PaginatedTenants, tenant_health(), TenantCreate (+7 more)

### Community 3 - "typing"
Cohesion: 0.08
Nodes (14): upgrade(), Base, set_sqlite_pragma(), Control, ControlMapping, Framework, Finding, FindingEvidence (+6 more)

### Community 4 - "AIRemediationEngine"
Cohesion: 0.08
Nodes (10): _run(), TestAIRemediationEngineFallback, TestAIRemediationEngineOpenAI, TestModuleLevelGenerateRemediation, TestNormalise, TestRuleBasedRemediation, AIRemediationEngine, generate_remediation() (+2 more)

### Community 5 - "dashboard.py"
Cohesion: 0.09
Nodes (31): ActivityItem, AuditEntry, AuditViewResponse, _build_framework_coverage(), CategoryBreakdown, ComplianceViewResponse, dashboard_audit(), dashboard_compliance() (+23 more)

### Community 6 - "NotificationDispatcher"
Cohesion: 0.09
Nodes (11): _db_result(), _make_dispatcher(), _make_settings_obj(), _run(), TestPublicAPI, TestSendSlackWebhook, TestSendSmtp, TestSendTeamsWebhook (+3 more)

### Community 8 - "test_core_logging.py"
Cohesion: 0.07
Nodes (16): _run(), TestCacheDelete, TestCacheGet, TestCacheKeyHelpers, TestCacheLifecycle, TestCacheSet, TestConfigureLogging, TestCorrelationId (+8 more)

### Community 9 - "FindingRepository"
Cohesion: 0.09
Nodes (17): AiRemediationRequest, FindingHistoryItem, FindingResponse, findings_summary(), FindingSummaryResponse, get_finding(), get_finding_history(), list_findings() (+9 more)

### Community 10 - "logging.py"
Cohesion: 0.06
Nodes (10): get_logger(), DefenderCollector, DefenderData, SharePointCollector, SharePointData, AWSSecretsManagerProvider, AggregatedHealthReport, check_all_providers() (+2 more)

### Community 12 - "annotations"
Cohesion: 0.05
Nodes (43): nginx.ingress.kubernetes.io/limit-rps, nginx.ingress.kubernetes.io/proxy-body-size, nginx.ingress.kubernetes.io/proxy-read-timeout, nginx.ingress.kubernetes.io/proxy-send-timeout, nginx.ingress.kubernetes.io/ssl-redirect, Ingress unimonitor, HorizontalPodAutoscaler unimonitor-api, HorizontalPodAutoscaler unimonitor-worker (+35 more)

### Community 13 - "test_worker_tasks.py"
Cohesion: 0.06
Nodes (23): _db_result(), _make_session_factory(), TestCleanupOldRuns, TestDispatchFindingAlert, TestGenerateReportTask, TestRunAssessmentTask, TestRunAsyncHelper, TestRunScheduledAssessments (+15 more)

### Community 14 - "package.json"
Cohesion: 0.07
Nodes (39): dependencies, axios@^1.6.5, clsx@^2.1.0, date-fns@^4.4.0, react-dom@^18.2.0, react-is@^19.3.1, react-router-dom@^6.21.3, @tanstack/react-query@^5.17.0 (+31 more)

### Community 15 - "setup_wizard.py"
Cohesion: 0.09
Nodes (8): _ask(), _confirm(), _print(), run_wizard(), setup_aws_secrets_manager(), setup_azure_key_vault(), setup_local_vault(), AzureKeyVaultProvider

### Community 16 - "security.py"
Cohesion: 0.10
Nodes (8): TestConstantTimeCompare, TestEncryptDecrypt, TestGenerateApiKey, constant_time_compare(), decrypt_secret(), encrypt_secret(), generate_api_key(), _get_fernet()

### Community 17 - "_make_engine"
Cohesion: 0.31
Nodes (4): _make_control_def(), _make_engine(), _run(), TestEvaluateControl

### Community 18 - "test_auth_and_cli.py"
Cohesion: 0.14
Nodes (13): TestCreateAccessToken, TestCreateRefreshToken, TestDecodeToken, TestValidateAccessToken, TestValidateRefreshToken, create_access_token(), create_refresh_token(), decode_refresh_token() (+5 more)

### Community 19 - "conftest.py"
Cohesion: 0.13
Nodes (9): admin_user(), auth_headers(), auth_token(), client(), db_session(), engine(), event_loop(), _session_factory() (+1 more)

### Community 20 - "grc.py"
Cohesion: 0.13
Nodes (15): control_crosswalk(), CrosswalkEntry, EvidenceResponse, EvidenceUploadResponse, framework_controls(), framework_coverage(), FrameworkCoverage, gap_analysis() (+7 more)

### Community 21 - "data"
Cohesion: 0.07
Nodes (31): apiVersion, data, kind, metadata, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CONTROLS_DIR, CORS_ORIGINS (+23 more)

### Community 22 - "test_api_auth.py"
Cohesion: 0.15
Nodes (15): test_callback_error_param(), test_callback_invalid_state(), test_entra_login_redirects(), test_get_me_authenticated(), test_get_me_bad_token(), test_get_me_unauthenticated(), test_login_inactive_user(), test_login_success() (+7 more)

### Community 23 - "AssessmentRun"
Cohesion: 0.08
Nodes (21): _assessment_to_response(), AssessmentCreate, AssessmentResponse, AssessmentUpdate, cancel_run(), create_assessment(), delete_assessment(), get_assessment() (+13 more)

### Community 24 - "GraphClient"
Cohesion: 0.06
Nodes (27): _run(), TestBatchGet, _test(), TestEnsureToken, _test(), _test(), _test(), TestGetAllPages (+19 more)

### Community 25 - "SecretMetadata"
Cohesion: 0.16
Nodes (3): TestRotationManager, SecretMetadata, RotationManager

### Community 26 - "reports.py"
Cohesion: 0.14
Nodes (11): delete_report(), download_report(), generate_report(), get_report_status(), list_report_runs(), list_reports(), PaginatedRunReports, ReportGenerateRequest (+3 more)

### Community 27 - "controls"
Cohesion: 0.09
Nodes (21): cis_controls_v8, cis_m365_benchmark, gdpr, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+13 more)

### Community 29 - "_run"
Cohesion: 0.23
Nodes (7): _make_provider(), _make_resolver(), _run(), TestHealthAndStats, TestResolveRef, TestSecretResolverGet, TestSecretResolverWrite

### Community 30 - "ControlLoader"
Cohesion: 0.16
Nodes (3): TestGRCJourney, TestControlLoader, ControlLoader

### Community 31 - "FrameworkCrosswalk"
Cohesion: 0.18
Nodes (3): _make_ctrl(), TestFrameworkCrosswalk, FrameworkCrosswalk

### Community 32 - "SecretResolver"
Cohesion: 0.17
Nodes (3): TestLocalVault, TestSecretResolver, SecretResolver

### Community 33 - "v1/notifications.py"
Cohesion: 0.17
Nodes (14): AlertThresholds, get_notification_settings(), _get_tenant(), _mask(), NotificationSettings, NotificationSettingsUpdate, SlackSettings, SmtpSettings (+6 more)

### Community 34 - "auth.py"
Cohesion: 0.09
Nodes (10): get_me(), login(), login_local(), logout(), oauth_callback(), refresh_token(), RefreshRequest, TokenResponse (+2 more)

### Community 36 - "generate_report_task"
Cohesion: 0.24
Nodes (3): ReportStatus, generate_report_task(), _run_async()

### Community 37 - "main.py"
Cohesion: 0.08
Nodes (12): AssessmentAlreadyRunningError, AssessmentError, ConflictError, DatabaseError, FrameworkNotFoundError, generic_exception_handler(), unimonitor_exception_handler(), UniMonitorError (+4 more)

### Community 38 - "App.tsx"
Cohesion: 0.17
Nodes (19): zustand@^5.1.0, App(), ProtectedRoute(), RouteErrorBoundary(), Layout(), NAV_ITEMS, AssessmentsPage(), AuditPage() (+11 more)

### Community 39 - "cli.py"
Cohesion: 0.13
Nodes (12): run_setup(), main(), migrate(), secrets_get(), _get(), secrets_health(), secrets_rotate(), _rotate() (+4 more)

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
Cohesion: 0.23
Nodes (6): cache_delete(), cache_delete_pattern(), cache_get(), cache_set(), close_cache(), get_redis()

### Community 47 - "get_current_user"
Cohesion: 0.17
Nodes (10): ComplianceMapping, ControlResponse, FrameworkControlSummary, FrameworkResponse, get_control(), get_framework(), list_controls(), list_frameworks() (+2 more)

### Community 48 - "get_secret_resolver"
Cohesion: 0.21
Nodes (5): TestGetSecretResolver, _check(), _set(), get_secret_resolver(), reset_resolver()

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
Cohesion: 0.13
Nodes (9): CollectionHistoryEntry, CollectorRunResponse, CollectorStatus, get_collection_history(), get_collectors(), get_platform_health(), PlatformHealthResponse, run_collector() (+1 more)

### Community 53 - "@tanstack/react-query"
Cohesion: 0.11
Nodes (18): lucide-react@^1.73.0, react@^18.2.0, findingsApi, reportsApi, queryClient, Finding, FindingListResponse, SEVERITIES (+10 more)

### Community 54 - "crosswalk.py"
Cohesion: 0.14
Nodes (6): TestCrosswalkFunctions, _build_index(), controls_for_framework(), crosswalk_for_control(), gap_analysis(), get_crosswalk_index()

### Community 56 - "compliance_mapping"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+11 more)

### Community 57 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+11 more)

### Community 58 - "main"
Cohesion: 0.14
Nodes (5): TestCliMigrate, TestCliSecrets, TestCliStart, main(), secrets()

### Community 61 - "controls"
Cohesion: 0.11
Nodes (18): cis_m365_benchmark, hipaa, iso27001_2022, nist_csf_2, soc2, zero_trust, controls, category (+10 more)

### Community 63 - "test_control_loader.py"
Cohesion: 0.17
Nodes (4): TestLoadAllControls, TestLoadControlsForFrameworks, load_all_controls(), load_controls_for_frameworks()

### Community 65 - "controls"
Cohesion: 0.10
Nodes (20): cis_controls_v8, gdpr, iso27001_2022, iso42001, nist_800_53_r5, nist_csf_2, soc2, zero_trust (+12 more)

### Community 66 - "get_settings"
Cohesion: 0.13
Nodes (9): TestGetAuthCodeUrl, TestGetMsalApp, TestGetMsalAppForTenant, build_authorize_url(), _exchange_code_for_token_sync(), get_auth_code_url(), get_msal_app(), get_msal_app_for_tenant() (+1 more)

### Community 67 - "controls"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, zero_trust, controls (+11 more)

### Community 68 - "compute_score"
Cohesion: 0.14
Nodes (3): TestFindingScoring, compute_framework_score(), compute_score()

### Community 69 - "acquire_token_for_client"
Cohesion: 0.26
Nodes (5): _run(), TestAcquireTokenForClient, TestExchangeCodeForToken, acquire_token_for_client(), exchange_code_for_token()

### Community 70 - "ports"
Cohesion: 0.16
Nodes (16): Service unimonitor-postgres, app, name, port, protocol, targetPort, app, matchLabels (+8 more)

### Community 72 - "smoke_test.py"
Cohesion: 0.22
Nodes (6): main(), run_smoke_tests(), test_authenticated_endpoints(), test_health(), test_login(), test_static_assets()

### Community 75 - "useApi.ts"
Cohesion: 0.22
Nodes (10): dashboardApi, monitoringApi, AuditEntry, CollectorRow(), CollectorStatus, SecurityDashboard(), ServiceCard, StatusIcon() (+2 more)

### Community 76 - "client.py"
Cohesion: 0.23
Nodes (8): TestGraphClientGet, TestGraphResponse, AuthenticationError, GraphAPIError, GraphPermissionError, GraphRateLimitError, GraphTimeoutError, GraphResponse

### Community 79 - "engine.py"
Cohesion: 0.13
Nodes (7): _make_finding(), TestCalculateFrameworkCoverage, TestCalculateScores, FindingSeverity, FindingState, calculate_framework_coverage(), calculate_scores()

### Community 80 - "@playwright/test"
Cohesion: 0.28
Nodes (4): loginAsAdmin(), loginViaApi(), TEST_ADMIN, @playwright/test

### Community 83 - "session.py"
Cohesion: 0.29
Nodes (3): create_all_tables(), drop_all_tables(), init_db()

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

### Community 88 - "require_role"
Cohesion: 0.11
Nodes (10): get_current_active_user(), require_admin(), require_analyst(), require_compliance(), require_role(), _check(), db_session_context(), get_async_session() (+2 more)

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
Cohesion: 0.19
Nodes (6): check_env(), create_default_admin(), generate_password(), main(), run_migrations(), seed_notification_settings()

### Community 106 - "_parse_legacy_format"
Cohesion: 0.29
Nodes (3): TestParseLegacyFormat, _load_yaml_file(), _parse_legacy_format()

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
Cohesion: 0.29
Nodes (7): assessmentsApi, Assessment, AssessmentCard(), AssessmentRun, FRAMEWORK_LABELS, FRAMEWORK_OPTIONS, RunStatusIcon()

### Community 122 - "ExecutiveDashboard.tsx"
Cohesion: 0.32
Nodes (7): ExecutiveDashboard(), FrameworkCoverage, ScoreGauge(), StatCard(), tooltipStyle, TopRisk, TrendPoint

### Community 123 - "compilerOptions"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

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

### Community 132 - "ComplianceDashboard.tsx"
Cohesion: 0.43
Nodes (6): recharts@^3.10.1, ComplianceDashboard(), FrameworkBar(), FrameworkCoverage, scoreColor(), recharts

### Community 133 - "SettingsPage.tsx"
Cohesion: 0.43
Nodes (6): api, FormField(), NotificationSettings, Section(), SettingsPage(), Toggle()

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

### Community 142 - "RiskDashboard.tsx"
Cohesion: 0.40
Nodes (5): cellColor(), LEVELS, RiskCell, RiskDashboard(), TopFinding

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

### Community 151 - "controls"
Cohesion: 0.11
Nodes (18): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, controls, category (+10 more)

### Community 177 - "get_audit_logger"
Cohesion: 0.22
Nodes (3): TestGetLogger, get_audit_logger(), log_audit_event()

## Knowledge Gaps
- **1 isolated node(s):** `unimonitor`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 1345 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **66 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GraphClient` connect `GraphClient` to `asyncio`, `.get`, `Tenant`, `RateLimiter`, `logging.py`, `client.py`, `monitoring.py`, `azure_security.py`, `copilot.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `GraphClient` (e.g. with `TestBatchGet` and `TestEnsureToken`) actually correct?**
  _`GraphClient` has 31 INFERRED edges - model-reasoned connections that need verification._
- **What connects `unimonitor` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `asyncio` be split into smaller, more focused modules?**
  _Cohesion score 0.08252853380158033 - nodes in this community are weakly interconnected._
- **Why does `get_settings()` connect `get_settings` to `config.py`, `auth.py`, `typing`, `RateLimiter`, `acquire_token_for_client`, `AIRemediationEngine`, `main.py`, `test_core_logging.py`, `logging.py`, `BaseReportGenerator`, `client.py`, `core/cache.py`, `security.py`, `test_auth_and_cli.py`, `grc.py`, `GraphClient`, `reports.py`, `._summary_stats`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `FindingRepository` (e.g. with `Finding` and `FindingEvidence`) actually correct?**
  _`FindingRepository` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Should `.get` be split into smaller, more focused modules?**
  _Cohesion score 0.08764568764568764 - nodes in this community are weakly interconnected._