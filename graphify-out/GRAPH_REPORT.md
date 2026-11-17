# Graph Report - cbb7236d17c7b011ebaca937  (2026-11-17)

## Corpus Check
- 215 files · ~119,341 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: (none) 7, .example 2, .ini 2)

## Summary
- 3722 nodes · 7611 edges · 211 communities (146 shown, 65 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 435 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `db62765d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- asyncio
- .get
- Tenant
- FindingRepository
- AIRemediationEngine
- dashboard.py
- NotificationDispatcher
- AsyncClient
- test_core_logging.py
- FindingRepository
- logging.py
- test_providers.py
- annotations
- AssessmentEngine
- package.json
- service.py
- security.py
- certificates.py
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
- .get
- get_secret_resolver
- ControlLoader
- FrameworkCrosswalk
- LocalVaultProvider
- CloudDashboard.tsx
- auth.py
- RateLimiter
- AssessmentRun
- main.py
- App.tsx
- client.py
- controls
- controls
- controls
- controls
- controls
- core/cache.py
- AzureKeyVaultProvider
- get_current_user
- _db_result
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
- test_control_loader.py
- config.py
- controls
- get_settings
- controls
- compute_score
- test_extended_collectors.py
- ports
- CsvReportGenerator
- AsyncClient
- TestDashboardJourney
- BaseReportGenerator
- useApi.ts
- get_logger
- TestLoginJourney
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
- dashboard_executive
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
- ControlDefinition
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
- test_worker_tasks.py
- DocxReportGenerator
- onboarding.py
- cleanup_old_runs
- unimonitor
- create_app
- TestIndividualCollectors
- ReportsPage.tsx
- tasks/notifications.py
- httpx
- Base
- load_controls_for_frameworks
- TestMonitoringJourney
- make_icon.py
- generate_report_task
- acquire_token_for_client
- PlatformConnector.tsx
- dependencies.py
- FakeGraph
- test_reports_api.py
- test_onboarding.py
- test_nsis_is_put_on_path_before_it_is_used
- .test_run_logs_start
- TestRunAsyncHelper
- TestCisoDashboard
- 001_initial_schema.py
- set_sqlite_pragma
- TestPermissions
- platform_catalogue

## God Nodes (most connected - your core abstractions)
1. `GraphClient` - 103 edges
2. `get_settings()` - 58 edges
3. `get_current_user()` - 58 edges
4. `FindingRepository` - 43 edges
5. `Tenant` - 39 edges
6. `_run()` - 39 edges
7. `AssessmentRepository` - 36 edges
8. `Base` - 36 edges
9. `SecretMetadata` - 36 edges
10. `get_logger()` - 36 edges

## Surprising Connections (you probably didn't know these)
- `TestConnectPlatforms` --uses--> `CloudError`  [INFERRED]
  tests/integration/test_onboarding_api.py → unimonitor/onboarding/clouds.py
- `TestEntraIdCollector` --uses--> `EntraIdCollector`  [INFERRED]
  tests/unit/test_graph_collectors.py → unimonitor/graph/collectors/entra_id.py
- `TestEntraIdCollector` --uses--> `EntraIdData`  [INFERRED]
  tests/unit/test_graph_collectors.py → unimonitor/graph/collectors/entra_id.py
- `TestDocxGenerator` --uses--> `DocxReportGenerator`  [INFERRED]
  tests/unit/test_reporting.py → unimonitor/reporting/docx_generator.py
- `TestProviderProtocolCompliance` --uses--> `SecretProvider`  [INFERRED]
  tests/unit/test_secrets.py → unimonitor/secrets/provider.py

## Import Cycles
- None detected.

## Communities (211 total, 65 thin omitted)

### Community 0 - "asyncio"
Cohesion: 0.13
Nodes (15): TestSafeGet, _collect_aws(), _collect_azure_security(), _collect_copilot(), _collect_defender(), _collect_entra_id(), _collect_exchange(), _collect_gcp() (+7 more)

### Community 1 - ".get"
Cohesion: 0.11
Nodes (16): _fail(), _make_client(), _ok(), _run(), TestEntraIdCollector, _get(), _get(), _get() (+8 more)

### Community 2 - "Tenant"
Cohesion: 0.09
Nodes (15): ConnectionTestResponse, create_tenant(), delete_tenant(), get_tenant(), list_tenants(), PaginatedTenants, tenant_health(), TenantCreate (+7 more)

### Community 3 - "FindingRepository"
Cohesion: 0.10
Nodes (3): Finding, FindingHistory, FindingRepository

### Community 4 - "AIRemediationEngine"
Cohesion: 0.08
Nodes (10): _run(), TestAIRemediationEngineFallback, TestAIRemediationEngineOpenAI, TestModuleLevelGenerateRemediation, TestNormalise, TestRuleBasedRemediation, AIRemediationEngine, generate_remediation() (+2 more)

### Community 5 - "dashboard.py"
Cohesion: 0.09
Nodes (35): ActivityItem, _build_framework_coverage(), CategoryBreakdown, CisoDashboardResponse, CisoRiskItem, CloudAggregateResponse, CloudProviderDetailResponse, CloudProviderSummary (+27 more)

### Community 6 - "NotificationDispatcher"
Cohesion: 0.09
Nodes (10): _db_result(), _make_dispatcher(), _make_settings_obj(), _run(), TestPublicAPI, TestSendSlackWebhook, TestSendSmtp, TestSendTeamsWebhook (+2 more)

### Community 7 - "AsyncClient"
Cohesion: 0.05
Nodes (6): TestAssessmentsAPI, TestAuthEndpoints, TestDashboardAPI, TestFindingsAPI, TestHealthEndpoint, TestReportsAPI

### Community 8 - "test_core_logging.py"
Cohesion: 0.07
Nodes (16): _run(), TestCacheDelete, TestCacheGet, TestCacheKeyHelpers, TestCacheLifecycle, TestCacheSet, TestConfigureLogging, TestCorrelationId (+8 more)

### Community 9 - "FindingRepository"
Cohesion: 0.14
Nodes (15): AiRemediationRequest, FindingHistoryItem, FindingResponse, findings_summary(), FindingSummaryResponse, get_finding(), get_finding_history(), list_findings() (+7 more)

### Community 10 - "logging.py"
Cohesion: 0.05
Nodes (18): TestGetLogger, get_audit_logger(), get_logger(), log_audit_event(), AzureSecurityCollector, AzureSecurityData, CopilotCollector, CopilotData (+10 more)

### Community 11 - "test_providers.py"
Cohesion: 0.16
Nodes (10): test_aliases_resolve(), test_provider_ids_cover_all_clouds(), test_service_maps_to_provider(), test_unknown_service_has_no_provider(), _group_by_provider(), _provider_controls_cached(), CloudProvider, get_provider() (+2 more)

### Community 12 - "annotations"
Cohesion: 0.05
Nodes (43): nginx.ingress.kubernetes.io/limit-rps, nginx.ingress.kubernetes.io/proxy-body-size, nginx.ingress.kubernetes.io/proxy-read-timeout, nginx.ingress.kubernetes.io/proxy-send-timeout, nginx.ingress.kubernetes.io/ssl-redirect, Ingress unimonitor, HorizontalPodAutoscaler unimonitor-api, HorizontalPodAutoscaler unimonitor-worker (+35 more)

### Community 13 - "AssessmentEngine"
Cohesion: 0.16
Nodes (8): AssessmentStatus, AssessmentEngine, run_assessment_task(), _run(), _run_async(), run_scheduled_assessments(), _run(), run_single_collector_task()

### Community 14 - "package.json"
Cohesion: 0.07
Nodes (39): dependencies, axios@^1.6.5, clsx@^2.1.0, date-fns@^4.4.0, lucide-react@^1.73.0, react-dom@^18.2.0, react-is@^19.3.1, @tanstack/react-query@^5.17.0 (+31 more)

### Community 15 - "service.py"
Cohesion: 0.13
Nodes (19): db_session_context(), CloudConnection, aws_credentials_for(), connect_google_service_account(), connect_microsoft(), connect_platform(), connection_dict(), create_first_admin() (+11 more)

### Community 16 - "security.py"
Cohesion: 0.10
Nodes (8): TestConstantTimeCompare, TestEncryptDecrypt, TestGenerateApiKey, constant_time_compare(), decrypt_secret(), encrypt_secret(), generate_api_key(), _get_fernet()

### Community 17 - "certificates.py"
Cohesion: 0.11
Nodes (8): TestCertificates, clamp_validity_days(), client_assertion(), _der_bytes(), generate_client_certificate(), graph_key_credential(), _sha1_digest(), thumbprint()

### Community 18 - "test_auth_and_cli.py"
Cohesion: 0.12
Nodes (12): TestCreateAccessToken, TestCreateRefreshToken, TestDecodeToken, TestGetMsalAppForTenant, TestValidateAccessToken, TestValidateRefreshToken, create_access_token(), create_refresh_token() (+4 more)

### Community 19 - "conftest.py"
Cohesion: 0.13
Nodes (9): admin_user(), auth_headers(), auth_token(), client(), db_session(), engine(), event_loop(), _session_factory() (+1 more)

### Community 20 - "grc.py"
Cohesion: 0.12
Nodes (16): control_crosswalk(), CrosswalkEntry, EvidenceResponse, EvidenceUploadResponse, framework_controls(), framework_coverage(), FrameworkCoverage, gap_analysis() (+8 more)

### Community 21 - "data"
Cohesion: 0.07
Nodes (31): apiVersion, data, kind, metadata, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CONTROLS_DIR, CORS_ORIGINS (+23 more)

### Community 22 - "test_api_auth.py"
Cohesion: 0.15
Nodes (15): test_callback_error_param(), test_callback_invalid_state(), test_entra_login_redirects(), test_get_me_authenticated(), test_get_me_bad_token(), test_get_me_unauthenticated(), test_login_inactive_user(), test_login_success() (+7 more)

### Community 23 - "AssessmentRun"
Cohesion: 0.10
Nodes (18): _assessment_to_response(), AssessmentCreate, AssessmentResponse, AssessmentUpdate, cancel_run(), create_assessment(), delete_assessment(), get_assessment() (+10 more)

### Community 24 - "GraphClient"
Cohesion: 0.08
Nodes (22): _run(), TestBatchGet, _test(), TestEnsureToken, _test(), _test(), _test(), TestGetAllPages (+14 more)

### Community 25 - "SecretMetadata"
Cohesion: 0.09
Nodes (4): _stub_azure_modules(), TestRotationManager, SecretMetadata, RotationManager

### Community 26 - "reports.py"
Cohesion: 0.10
Nodes (12): delete_report(), download_report(), generate_report(), get_report_status(), list_report_runs(), list_reports(), PaginatedRunReports, ReportGenerateRequest (+4 more)

### Community 27 - "controls"
Cohesion: 0.09
Nodes (21): cis_controls_v8, cis_m365_benchmark, gdpr, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+13 more)

### Community 28 - ".get"
Cohesion: 0.25
Nodes (3): TestEntraIdDataclass, EntraIdCollector, EntraIdData

### Community 29 - "get_secret_resolver"
Cohesion: 0.06
Nodes (29): main(), run_smoke_tests(), test_authenticated_endpoints(), test_health(), test_login(), test_static_assets(), _make_provider(), _make_resolver() (+21 more)

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
Cohesion: 0.29
Nodes (7): cardStyle, CloudDashboard(), CloudsResponse, FindingCounts, ProviderSummary, scoreColor(), StateCounts

### Community 34 - "auth.py"
Cohesion: 0.10
Nodes (9): get_me(), login_local(), logout(), oauth_callback(), refresh_token(), RefreshRequest, TokenResponse, UserProfile (+1 more)

### Community 37 - "main.py"
Cohesion: 0.11
Nodes (5): close_cache(), lifespan(), _setup_otel(), _spa_directory(), SpaFallbackMiddleware

### Community 38 - "App.tsx"
Cohesion: 0.18
Nodes (15): react-router-dom@^6.21.3, zustand@^5.1.0, ProtectedRoute(), Layout(), NAV_ITEMS, api, LoginPage(), AuthState (+7 more)

### Community 39 - "client.py"
Cohesion: 0.24
Nodes (6): TestGraphResponse, GraphAPIError, GraphPermissionError, GraphRateLimitError, GraphTimeoutError, GraphResponse

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
Cohesion: 0.27
Nodes (5): cache_delete(), cache_delete_pattern(), cache_get(), cache_set(), get_redis()

### Community 46 - "AzureKeyVaultProvider"
Cohesion: 0.12
Nodes (3): TestBuildProvider, AzureKeyVaultProvider, _build_provider()

### Community 47 - "get_current_user"
Cohesion: 0.17
Nodes (10): ComplianceMapping, ControlResponse, FrameworkControlSummary, FrameworkResponse, get_control(), get_framework(), list_controls(), list_frameworks() (+2 more)

### Community 48 - "_db_result"
Cohesion: 0.24
Nodes (5): _db_result(), TestDispatchFindingAlert, TestRunSingleCollectorTask, dispatch_finding_alert(), _run()

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
Cohesion: 0.20
Nodes (8): CollectionHistoryEntry, CollectorRunResponse, CollectorStatus, get_collection_history(), get_collectors(), get_platform_health(), PlatformHealthResponse, run_collector()

### Community 53 - "v1/notifications.py"
Cohesion: 0.17
Nodes (14): AlertThresholds, get_notification_settings(), _get_tenant(), _mask(), NotificationSettings, NotificationSettingsUpdate, SlackSettings, SmtpSettings (+6 more)

### Community 54 - "CloudError"
Cohesion: 0.12
Nodes (9): _bootstrap(), TestConnectPlatforms, fake_aws(), fake_gcp(), fake_start(), TestFirstRunWindow, TestMicrosoftCertificateFallback, fake_provision() (+1 more)

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
Cohesion: 0.11
Nodes (4): _run(), TestAWSSecretsManagerProvider, TestAzureKeyVaultProvider, AWSSecretsManagerProvider

### Community 61 - "controls"
Cohesion: 0.11
Nodes (18): cis_m365_benchmark, hipaa, iso27001_2022, nist_csf_2, soc2, zero_trust, controls, category (+10 more)

### Community 63 - "test_control_loader.py"
Cohesion: 0.12
Nodes (5): TestLoadAllControls, TestParseLegacyFormat, load_all_controls(), _load_yaml_file(), _parse_legacy_format()

### Community 64 - "config.py"
Cohesion: 0.10
Nodes (3): login(), _load_or_create_secret_key(), Settings

### Community 65 - "controls"
Cohesion: 0.10
Nodes (20): cis_controls_v8, gdpr, iso27001_2022, iso42001, nist_800_53_r5, nist_csf_2, soc2, zero_trust (+12 more)

### Community 66 - "get_settings"
Cohesion: 0.12
Nodes (11): TestGetAuthCodeUrl, TestGetMsalApp, acquire_token_for_client(), build_authorize_url(), client_credential(), _exchange_code_for_token_sync(), get_auth_code_url(), get_msal_app() (+3 more)

### Community 67 - "controls"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, iso27001_2022, nist_800_53_r5, nist_csf_2, soc2, zero_trust, controls (+11 more)

### Community 68 - "compute_score"
Cohesion: 0.14
Nodes (3): TestFindingScoring, compute_framework_score(), compute_score()

### Community 69 - "test_extended_collectors.py"
Cohesion: 0.09
Nodes (19): evaluate(), _new_control_ids(), _run(), test_all_new_controls_return_canonical_states(), test_application_inventory_controls_evaluate(), test_cloud_apps_controls_evaluate(), test_copilot_studio_controls_evaluate(), test_defender_identity_controls_evaluate() (+11 more)

### Community 70 - "ports"
Cohesion: 0.16
Nodes (16): Service unimonitor-postgres, app, name, port, protocol, targetPort, app, matchLabels (+8 more)

### Community 75 - "useApi.ts"
Cohesion: 0.10
Nodes (19): dashboardApi, monitoringApi, queryClient, AuditEntry, AuditPage(), cellColor(), LEVELS, RiskCell (+11 more)

### Community 76 - "get_logger"
Cohesion: 0.07
Nodes (8): check(), fetch(), free_port(), main(), AggregatedHealthReport, check_all_providers(), HealthStatus, ProviderType

### Community 79 - "test_crosswalk.py"
Cohesion: 0.06
Nodes (19): _make_finding(), TestCalculateFrameworkCoverage, TestCalculateScores, TestCrosswalkFunctions, _make_control_def(), _make_engine(), _make_run(), _run() (+11 more)

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
Cohesion: 0.13
Nodes (15): _check(), AssessmentAlreadyRunningError, AssessmentError, AuthenticationError, AuthorisationError, ConflictError, DatabaseError, FrameworkNotFoundError (+7 more)

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
Cohesion: 0.11
Nodes (14): App(), RouteErrorBoundary(), SetupGate(), DefaultFallback(), ErrorBoundary, Props, State, findingsApi (+6 more)

### Community 94 - "hooks"
Cohesion: 0.18
Nodes (10): additional_dependencies, args, exclude, files, id, stages, repos, hooks (+2 more)

### Community 95 - "CollectorRegistry"
Cohesion: 0.19
Nodes (6): _make_gc(), _run(), TestCollectAll, TestRunCollector, CollectorRegistry, _run()

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

### Community 103 - "dashboard_executive"
Cohesion: 0.10
Nodes (14): AuditEntry, AuditViewResponse, ComplianceViewResponse, dashboard_audit(), dashboard_compliance(), dashboard_executive(), dashboard_risk(), dashboard_trends() (+6 more)

### Community 105 - "m365.py"
Cohesion: 0.18
Nodes (11): add_certificate(), _client(), _graph(), M365Error, poll_device_flow(), provision_app(), ProvisionResult, _resolve_role_ids() (+3 more)

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
Cohesion: 0.18
Nodes (13): recharts@^3.10.1, ComplianceDashboard(), FrameworkBar(), FrameworkCoverage, scoreColor(), ExecutiveDashboard(), FrameworkCoverage, ScoreGauge() (+5 more)

### Community 123 - "compilerOptions"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 126 - "test_windows_build_assets.py"
Cohesion: 0.14
Nodes (8): _spec_hiddenimports(), test_docker_images_copy_the_package_before_installing(), test_nsis_does_not_require_third_party_plugins(), test_nsis_icon_exists(), test_release_workflow_builds_installer_on_demand(), test_spec_does_not_reference_removed_secrets_factory(), test_spec_hiddenimports_point_at_real_unimonitor_modules(), test_standalone_installer_workflow_is_dispatchable()

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
Cohesion: 0.08
Nodes (23): aws_data(), _BotoClient, _BotoSession, evaluate(), _FakeHTTP, gcp_data(), gws_data(), _run() (+15 more)

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
Cohesion: 0.12
Nodes (6): _isolated_vault(), controls(), test_every_control_evaluates(), FrameworkMeta, get_framework(), list_frameworks()

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

### Community 154 - "test_worker_tasks.py"
Cohesion: 0.15
Nodes (7): _make_session_factory(), TestGenerateReportTask, TestRunScheduledAssessments, TestSendDailyDigests, TestSendWeeklyDigests, send_daily_digests(), _run()

### Community 157 - "onboarding.py"
Cohesion: 0.09
Nodes (14): _certificate_payload(), CompleteRequest, connect(), connect_google_service_account(), create_admin(), FirstAdmin, GoogleServiceAccountRequest, microsoft_complete() (+6 more)

### Community 176 - "create_app"
Cohesion: 0.15
Nodes (3): _build_spa(), TestSpaServing, create_app()

### Community 178 - "ReportsPage.tsx"
Cohesion: 0.29
Nodes (7): reportsApi, FORMAT_LABELS, FORMAT_OPTIONS, Report, ReportsPage(), RunReportSummary, StatusIcon()

### Community 179 - "tasks/notifications.py"
Cohesion: 0.18
Nodes (3): _run_async(), send_weekly_digests(), _run()

### Community 180 - "httpx"
Cohesion: 0.09
Nodes (16): fake_validate(), fake_validate(), assume_role_credentials(), _call(), _boto3(), CloudError, _google_token(), validate_aws() (+8 more)

### Community 181 - "Base"
Cohesion: 0.10
Nodes (11): Base, AuditLog, Control, ControlMapping, Framework, FindingEvidence, NotificationSetting, Report (+3 more)

### Community 188 - "generate_report_task"
Cohesion: 0.22
Nodes (3): ReportStatus, generate_report_task(), _run_async()

### Community 189 - "acquire_token_for_client"
Cohesion: 0.18
Nodes (6): _run(), TestAcquireTokenForClient, TestExchangeCodeForToken, TestGetEntraUserInfo, exchange_code_for_token(), get_entra_user_info()

### Community 190 - "PlatformConnector.tsx"
Cohesion: 0.11
Nodes (29): react@^18.2.0, AuthMethodPicker(), Certificate, CertificateFiles, Connection, DeviceCode, Field(), GoogleSharedConnector() (+21 more)

### Community 191 - "dependencies.py"
Cohesion: 0.14
Nodes (5): get_current_active_user(), create_all_tables(), drop_all_tables(), get_async_session(), AppUser

### Community 193 - "test_reports_api.py"
Cohesion: 0.16
Nodes (3): _make_run(), TestGenerateReport, Assessment

### Community 194 - "test_onboarding.py"
Cohesion: 0.09
Nodes (7): _graph_mock(), handler(), _rsa_key(), TestGoogleServiceAccounts, TestMicrosoftSetup, reset_cache(), GraphPermission

## Knowledge Gaps
- **1 isolated node(s):** `unimonitor`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 1597 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **65 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GraphClient` connect `GraphClient` to `asyncio`, `.get`, `Tenant`, `get_settings`, `RateLimiter`, `client.py`, `logging.py`, `extended.py`, `monitoring.py`, `dependencies.py`, `.get`, `CollectorRegistry`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `GraphClient` (e.g. with `TestBatchGet` and `TestEnsureToken`) actually correct?**
  _`GraphClient` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `unimonitor` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `asyncio` be split into smaller, more focused modules?**
  _Cohesion score 0.13090418353576247 - nodes in this community are weakly interconnected._
- **Why does `get_settings()` connect `get_settings` to `test_cloud_providers.py`, `AIRemediationEngine`, `test_core_logging.py`, `logging.py`, `service.py`, `security.py`, `test_auth_and_cli.py`, `grc.py`, `reports.py`, `onboarding.py`, `auth.py`, `RateLimiter`, `main.py`, `client.py`, `core/cache.py`, `create_app`, `tasks/notifications.py`, `httpx`, `Base`, `config.py`, `test_extended_collectors.py`, `BaseReportGenerator`, `dependencies.py`, `test_reporting.py`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Should `.get` be split into smaller, more focused modules?**
  _Cohesion score 0.1054421768707483 - nodes in this community are weakly interconnected._
- **Why does `get_current_user()` connect `get_current_user` to `auth.py`, `Tenant`, `dashboard.py`, `dashboard_executive`, `FindingRepository`, `test_auth_and_cli.py`, `grc.py`, `monitoring.py`, `v1/notifications.py`, `AssessmentRun`, `dependencies.py`, `reports.py`, `dependencies.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._