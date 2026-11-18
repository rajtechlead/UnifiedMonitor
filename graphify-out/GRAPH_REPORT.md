# Graph Report - cbb7236d17c7b011ebaca937  (2026-11-18)

## Corpus Check
- 234 files · ~135,777 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: (none) 7, .example 2, .ini 2)

## Summary
- 4014 nodes · 8388 edges · 216 communities (150 shown, 66 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 450 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ef9e5516`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- asyncio
- .get
- Tenant
- dashboard_overview
- AIRemediationEngine
- dashboard.py
- NotificationDispatcher
- AsyncClient
- test_core_logging.py
- FindingRepository
- resolver.py
- test_providers.py
- annotations
- tasks/assessment.py
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
- test_crosswalk.py
- _run
- ControlLoader
- FrameworkCrosswalk
- LocalVaultProvider
- NotificationDispatcher
- auth.py
- RateLimiter
- v1/alerts.py
- AssessmentRun
- App.tsx
- crosswalk.py
- controls
- controls
- controls
- controls
- controls
- core/cache.py
- search.py
- get_current_user
- _make_session_factory
- controls
- controls
- controls
- monitoring.py
- v1/notifications.py
- CloudError
- SecretCache
- compliance_mapping
- compilerOptions
- cli.py
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
- pathlib
- TestLoginJourney
- _normalise
- _make_engine
- @playwright/test
- SecretProvider
- ExcelReportGenerator
- typing
- controls
- controls
- controls
- labels
- client.py
- env.py
- containers
- labels
- containers
- lucide-react
- hooks
- alerts/engine.py
- ControlDefinition
- test_reporting.py
- services
- db
- containers
- scripts
- test_onboarding.py
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
- test_cloud_providers.py
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
- _FakeHTTP
- CisoDashboard.tsx
- CloudProviderPage.tsx
- controls
- db
- initContainers
- spec
- test_merged_features.py
- Secret unimonitor-postgres-secret
- volumeClaimTemplates
- extended.py
- TestIndividualCollectors
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
- tasks/notifications.py
- DocxReportGenerator
- onboarding.py
- cloud_providers.py
- unimonitor
- create_app
- oauth_callback
- ReportsPage.tsx
- ExecutiveDashboard.tsx
- httpx
- Base
- cleanup_old_runs
- TestMonitoringJourney
- RiskDashboard.tsx
- _BotoClient
- TestPermissions
- generate_report_task
- acquire_token_for_client
- PlatformConnector.tsx
- dependencies.py
- FindingsPage.tsx
- pillar_for
- google_auth.py
- TestCisoDashboard
- platform_catalogue
- logging.py

## God Nodes (most connected - your core abstractions)
1. `GraphClient` - 104 edges
2. `get_current_user()` - 73 edges
3. `get_settings()` - 64 edges
4. `FindingRepository` - 45 edges
5. `require_role()` - 45 edges
6. `Base` - 39 edges
7. `Finding` - 39 edges
8. `_run()` - 39 edges
9. `Tenant` - 38 edges
10. `get_logger()` - 37 edges

## Surprising Connections (you probably didn't know these)
- `TestPublicAPI` --uses--> `NotificationDispatcher`  [INFERRED]
  tests/unit/test_notifications_dispatcher.py → unimonitor/notifications/dispatcher.py
- `TestAWSSecretsManagerProvider` --uses--> `AWSSecretsManagerProvider`  [INFERRED]
  tests/unit/test_secrets_backends.py → unimonitor/secrets/aws_secrets_manager.py
- `TestAzureKeyVaultProvider` --uses--> `AzureKeyVaultProvider`  [INFERRED]
  tests/unit/test_secrets_backends.py → unimonitor/secrets/azure_keyvault.py
- `TestAzureKeyVaultProvider` --uses--> `ProviderType`  [INFERRED]
  tests/unit/test_secrets_backends.py → unimonitor/secrets/provider.py
- `TestRotationManager` --uses--> `ProviderType`  [INFERRED]
  tests/unit/test_secrets_backends.py → unimonitor/secrets/provider.py

## Import Cycles
- None detected.

## Communities (216 total, 66 thin omitted)

### Community 0 - "asyncio"
Cohesion: 0.09
Nodes (21): _make_gc(), _run(), TestCollectAll, TestRunCollector, TestSafeGet, _collect_aws(), _collect_azure_security(), _collect_copilot() (+13 more)

### Community 1 - ".get"
Cohesion: 0.09
Nodes (19): _fail(), _make_client(), _ok(), _run(), TestEntraIdCollector, _get(), _get(), _get() (+11 more)

### Community 2 - "Tenant"
Cohesion: 0.10
Nodes (14): ConnectionTestResponse, create_tenant(), delete_tenant(), get_tenant(), list_tenants(), PaginatedTenants, tenant_health(), TenantCreate (+6 more)

### Community 3 - "dashboard_overview"
Cohesion: 0.11
Nodes (14): _build_framework_coverage(), dashboard_audit(), dashboard_compliance(), dashboard_executive(), dashboard_overview(), dashboard_risk(), dashboard_security(), dashboard_soc() (+6 more)

### Community 4 - "AIRemediationEngine"
Cohesion: 0.08
Nodes (10): _run(), TestAIRemediationEngineFallback, TestAIRemediationEngineOpenAI, TestModuleLevelGenerateRemediation, TestNormalise, TestRuleBasedRemediation, AIRemediationEngine, generate_remediation() (+2 more)

### Community 5 - "dashboard.py"
Cohesion: 0.09
Nodes (42): ActivityItem, AuditChainResponse, AuditEntry, AuditViewResponse, CategoryBreakdown, CisoDashboardResponse, CisoRiskItem, CloudAggregateResponse (+34 more)

### Community 6 - "NotificationDispatcher"
Cohesion: 0.16
Nodes (9): _db_result(), _make_dispatcher(), _make_settings_obj(), _run(), TestPublicAPI, TestSendSlackWebhook, TestSendSmtp, TestSendTeamsWebhook (+1 more)

### Community 7 - "AsyncClient"
Cohesion: 0.05
Nodes (6): TestAssessmentsAPI, TestAuthEndpoints, TestDashboardAPI, TestFindingsAPI, TestHealthEndpoint, TestReportsAPI

### Community 8 - "test_core_logging.py"
Cohesion: 0.06
Nodes (17): _run(), TestCacheDelete, TestCacheGet, TestCacheKeyHelpers, TestCacheLifecycle, TestCacheSet, TestConfigureLogging, TestCorrelationId (+9 more)

### Community 9 - "FindingRepository"
Cohesion: 0.09
Nodes (23): AiRemediationRequest, finding_timeline(), FindingHistoryItem, FindingResponse, findings_summary(), FindingSummaryResponse, get_finding(), get_finding_history() (+15 more)

### Community 10 - "resolver.py"
Cohesion: 0.06
Nodes (8): TestBuildProvider, AWSSecretsManagerProvider, AzureKeyVaultProvider, AggregatedHealthReport, check_all_providers(), HealthStatus, ProviderType, _build_provider()

### Community 11 - "test_providers.py"
Cohesion: 0.20
Nodes (8): test_aliases_resolve(), test_provider_ids_cover_all_clouds(), test_service_maps_to_provider(), test_unknown_service_has_no_provider(), CloudProvider, get_provider(), provider_for_service(), provider_ids()

### Community 12 - "annotations"
Cohesion: 0.05
Nodes (43): nginx.ingress.kubernetes.io/limit-rps, nginx.ingress.kubernetes.io/proxy-body-size, nginx.ingress.kubernetes.io/proxy-read-timeout, nginx.ingress.kubernetes.io/proxy-send-timeout, nginx.ingress.kubernetes.io/ssl-redirect, Ingress unimonitor, HorizontalPodAutoscaler unimonitor-api, HorizontalPodAutoscaler unimonitor-worker (+35 more)

### Community 13 - "tasks/assessment.py"
Cohesion: 0.11
Nodes (9): TestRunAsyncHelper, TestRunScheduledAssessments, TestRunSingleCollectorTask, collect_all_tenants(), run_assessment_task(), _run(), _run_async(), run_scheduled_assessments() (+1 more)

### Community 14 - "package.json"
Cohesion: 0.07
Nodes (39): dependencies, axios@^1.6.5, clsx@^2.1.0, date-fns@^4.4.0, lucide-react@^1.73.0, react-dom@^18.2.0, react-is@^19.3.1, @tanstack/react-query@^5.17.0 (+31 more)

### Community 15 - "service.py"
Cohesion: 0.11
Nodes (21): microsoft_complete(), db_session_context(), CloudConnection, aws_credentials_for(), connect_google_service_account(), connect_microsoft(), connect_platform(), connection_dict() (+13 more)

### Community 16 - "security.py"
Cohesion: 0.10
Nodes (8): TestConstantTimeCompare, TestEncryptDecrypt, TestGenerateApiKey, constant_time_compare(), decrypt_secret(), encrypt_secret(), generate_api_key(), _get_fernet()

### Community 17 - "certificates.py"
Cohesion: 0.09
Nodes (12): fake_remove(), TestCertificateHousekeeping, handler(), TestCertificates, clamp_validity_days(), client_assertion(), _der_bytes(), expiry() (+4 more)

### Community 18 - "test_auth_and_cli.py"
Cohesion: 0.14
Nodes (11): TestCreateAccessToken, TestCreateRefreshToken, TestDecodeToken, TestValidateAccessToken, TestValidateRefreshToken, create_access_token(), create_refresh_token(), decode_refresh_token() (+3 more)

### Community 19 - "conftest.py"
Cohesion: 0.09
Nodes (10): admin_user(), auth_headers(), auth_token(), client(), db_session(), engine(), event_loop(), _session_factory() (+2 more)

### Community 20 - "grc.py"
Cohesion: 0.12
Nodes (17): control_crosswalk(), CrosswalkEntry, EvidenceResponse, EvidenceUploadResponse, framework_controls(), framework_coverage(), FrameworkCoverage, gap_analysis() (+9 more)

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
Nodes (24): _run(), TestBatchGet, _test(), TestEnsureToken, _test(), _test(), _test(), TestGetAllPages (+16 more)

### Community 25 - "SecretMetadata"
Cohesion: 0.08
Nodes (4): _stub_azure_modules(), TestRotationManager, SecretMetadata, RotationManager

### Community 26 - "reports.py"
Cohesion: 0.12
Nodes (15): delete_report(), download_report(), download_report_format(), _file_response(), generate_report(), get_report_status(), list_report_runs(), list_reports() (+7 more)

### Community 27 - "controls"
Cohesion: 0.09
Nodes (21): cis_controls_v8, cis_m365_benchmark, gdpr, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+13 more)

### Community 28 - "test_crosswalk.py"
Cohesion: 0.16
Nodes (5): _make_finding(), TestCalculateFrameworkCoverage, TestCalculateScores, calculate_framework_coverage(), calculate_scores()

### Community 29 - "_run"
Cohesion: 0.15
Nodes (9): _make_provider(), _make_resolver(), _run(), TestGetSecretResolver, TestHealthAndStats, TestResolveRef, TestSecretResolverGet, TestSecretResolverWrite (+1 more)

### Community 30 - "ControlLoader"
Cohesion: 0.16
Nodes (3): TestGRCJourney, TestControlLoader, ControlLoader

### Community 31 - "FrameworkCrosswalk"
Cohesion: 0.18
Nodes (3): _make_ctrl(), TestFrameworkCrosswalk, FrameworkCrosswalk

### Community 32 - "LocalVaultProvider"
Cohesion: 0.09
Nodes (5): TestLocalVault, TestProviderProtocolCompliance, TestSecretResolver, LocalVaultProvider, SecretResolver

### Community 34 - "auth.py"
Cohesion: 0.13
Nodes (7): get_me(), login_local(), logout(), refresh_token(), RefreshRequest, TokenResponse, UserProfile

### Community 36 - "v1/alerts.py"
Cohesion: 0.19
Nodes (20): alert_summary(), AlertPage, AlertResponse, AlertSummary, AlertUpdateRequest, create_policy(), create_policy_from_template(), delete_policy() (+12 more)

### Community 37 - "AssessmentRun"
Cohesion: 0.11
Nodes (7): _make_run(), TestGenerateReport, Assessment, AssessmentRun, AssessmentRunRepository, _run(), _run()

### Community 38 - "App.tsx"
Cohesion: 0.12
Nodes (24): react-router-dom@^6.21.3, zustand@^5.1.0, App(), ProtectedRoute(), RouteErrorBoundary(), SetupGate(), Layout(), NAV_ITEMS (+16 more)

### Community 39 - "crosswalk.py"
Cohesion: 0.14
Nodes (6): TestCrosswalkFunctions, _build_index(), controls_for_framework(), crosswalk_for_control(), gap_analysis(), get_crosswalk_index()

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

### Community 46 - "search.py"
Cohesion: 0.13
Nodes (6): global_search(), SearchHit, SearchResponse, create_all_tables(), drop_all_tables(), get_async_session()

### Community 47 - "get_current_user"
Cohesion: 0.20
Nodes (9): ComplianceMapping, ControlResponse, FrameworkControlSummary, FrameworkResponse, get_control(), get_framework(), list_controls(), list_frameworks() (+1 more)

### Community 48 - "_make_session_factory"
Cohesion: 0.10
Nodes (11): _db_result(), _make_session_factory(), TestDispatchFindingAlert, TestGenerateReportTask, TestNotificationTaskArguments, fake_digest(), TestRunAssessmentTask, TestSendDailyDigests (+3 more)

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
Cohesion: 0.12
Nodes (21): collect_now(), CollectionHistoryEntry, CollectionScheduleResponse, CollectNowResponse, CollectorRunResponse, CollectorStatus, get_collection_history(), get_collection_schedule() (+13 more)

### Community 53 - "v1/notifications.py"
Cohesion: 0.15
Nodes (14): AlertThresholds, get_notification_settings(), _get_tenant(), _mask(), NotificationSettings, NotificationSettingsUpdate, SlackSettings, SmtpSettings (+6 more)

### Community 54 - "CloudError"
Cohesion: 0.08
Nodes (14): _bootstrap(), TestCertificateRotation, fake_app_id(), fake_token(), forbidden(), TestConnectPlatforms, fake_aws(), fake_gcp() (+6 more)

### Community 55 - "SecretCache"
Cohesion: 0.09
Nodes (3): TestSecretCache, _CacheEntry, SecretCache

### Community 56 - "compliance_mapping"
Cohesion: 0.10
Nodes (19): cis_controls_v8, cis_m365_benchmark, cmmc_2, hipaa, iso27001_2022, nist_800_53_r5, nist_csf_2, pci_dss_v4 (+11 more)

### Community 57 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+11 more)

### Community 58 - "cli.py"
Cohesion: 0.05
Nodes (24): main(), run_smoke_tests(), test_authenticated_endpoints(), test_health(), test_login(), test_static_assets(), TestCliMigrate, TestCliSecrets (+16 more)

### Community 59 - "_run"
Cohesion: 0.14
Nodes (3): _run(), TestAWSSecretsManagerProvider, TestAzureKeyVaultProvider

### Community 61 - "controls"
Cohesion: 0.11
Nodes (18): cis_m365_benchmark, hipaa, iso27001_2022, nist_csf_2, soc2, zero_trust, controls, category (+10 more)

### Community 63 - "test_control_loader.py"
Cohesion: 0.11
Nodes (7): TestLoadAllControls, TestLoadControlsForFrameworks, TestParseLegacyFormat, load_all_controls(), load_controls_for_frameworks(), _load_yaml_file(), _parse_legacy_format()

### Community 65 - "controls"
Cohesion: 0.10
Nodes (20): cis_controls_v8, gdpr, iso27001_2022, iso42001, nist_800_53_r5, nist_csf_2, soc2, zero_trust (+12 more)

### Community 66 - "get_settings"
Cohesion: 0.11
Nodes (11): TestGetAuthCodeUrl, TestGetMsalApp, TestGetMsalAppForTenant, build_authorize_url(), client_credential(), _exchange_code_for_token_sync(), get_auth_code_url(), get_msal_app() (+3 more)

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
Cohesion: 0.21
Nodes (13): app, name, port, protocol, targetPort, app, matchLabels, spec (+5 more)

### Community 75 - "useApi.ts"
Cohesion: 0.08
Nodes (29): Hit, PAGES, dashboardApi, monitoringApi, searchApi, AuditEntry, ChainCheck, Licensing (+21 more)

### Community 76 - "pathlib"
Cohesion: 0.11
Nodes (6): draw_icon(), main(), check(), fetch(), free_port(), main()

### Community 79 - "_make_engine"
Cohesion: 0.19
Nodes (6): _make_control_def(), _make_engine(), _make_run(), _run(), TestAssessmentEngineRun, TestEvaluateControl

### Community 80 - "@playwright/test"
Cohesion: 0.28
Nodes (4): loginAsAdmin(), loginViaApi(), TEST_ADMIN, @playwright/test

### Community 83 - "typing"
Cohesion: 0.09
Nodes (8): AssessmentStatus, Finding, FindingEvidence, FindingHistory, FindingSeverity, FindingState, AssessmentEngine, evaluate_one()

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
Cohesion: 0.33
Nodes (9): metadata, app, app.kubernetes.io/component, app.kubernetes.io/name, labels, name, namespace, metadata (+1 more)

### Community 88 - "client.py"
Cohesion: 0.10
Nodes (19): AssessmentAlreadyRunningError, AssessmentError, AuthenticationError, ConflictError, DatabaseError, FrameworkNotFoundError, generic_exception_handler(), GraphAPIError (+11 more)

### Community 89 - "env.py"
Cohesion: 0.22
Nodes (4): do_run_migrations(), run_async_migrations(), run_migrations_offline(), run_migrations_online()

### Community 90 - "containers"
Cohesion: 0.18
Nodes (11): envFrom, image, imagePullPolicy, livenessProbe, name, ports, readinessProbe, resources (+3 more)

### Community 91 - "labels"
Cohesion: 0.17
Nodes (16): Service unimonitor-api, StatefulSet unimonitor-postgres, app, app.kubernetes.io/component, app.kubernetes.io/name, labels, name, namespace (+8 more)

### Community 92 - "containers"
Cohesion: 0.18
Nodes (11): command, envFrom, image, imagePullPolicy, livenessProbe, name, ports, resources (+3 more)

### Community 93 - "lucide-react"
Cohesion: 0.09
Nodes (18): react@^18.2.0, DefaultFallback(), ErrorBoundary, Props, State, alertsApi, Alert, AlertSummary (+10 more)

### Community 94 - "hooks"
Cohesion: 0.18
Nodes (10): additional_dependencies, args, exclude, files, id, stages, repos, hooks (+2 more)

### Community 95 - "alerts/engine.py"
Cohesion: 0.17
Nodes (7): _compares(), evaluate_tenant(), metric_value(), serialize_policy(), AlertKind, AlertStatus, TriageStatus

### Community 99 - "services"
Cohesion: 0.20
Nodes (9): networks, unimonitor_net, services, driver, version, volumes, postgres_data, redis_data (+1 more)

### Community 100 - "db"
Cohesion: 0.20
Nodes (10): container_name, environment, image, networks, restart, volumes, POSTGRES_DB, POSTGRES_PASSWORD (+2 more)

### Community 101 - "containers"
Cohesion: 0.22
Nodes (9): env, image, name, ports, resources, volumeMounts, automountServiceAccountToken, containers (+1 more)

### Community 102 - "scripts"
Cohesion: 0.20
Nodes (10): scripts, build, dev, lint, preview, test:e2e, test:e2e:report, test:e2e:smoke (+2 more)

### Community 103 - "test_onboarding.py"
Cohesion: 0.08
Nodes (10): fake_provision(), _graph_mock(), handler(), _rsa_key(), TestGoogleServiceAccounts, TestMicrosoftSetup, reset_cache(), provision_app() (+2 more)

### Community 105 - "m365.py"
Cohesion: 0.10
Nodes (16): TestSignInClient, add_certificate(), _client(), client_credentials_token(), find_app_object_id(), _friendly(), _graph(), M365Error (+8 more)

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
Cohesion: 0.20
Nodes (10): fsGroup, runAsNonRoot, runAsUser, automountServiceAccountToken, securityContext, serviceAccountName, volumes, spec (+2 more)

### Community 113 - "labels"
Cohesion: 0.21
Nodes (13): apiVersion, kind, metadata, metadata, metadata, Deployment unimonitor-beat, app, app.kubernetes.io/component (+5 more)

### Community 114 - "spec"
Cohesion: 0.20
Nodes (10): fsGroup, runAsNonRoot, runAsUser, automountServiceAccountToken, securityContext, serviceAccountName, volumes, spec (+2 more)

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

### Community 119 - "test_cloud_providers.py"
Cohesion: 0.26
Nodes (7): evaluate(), test_aws_controls_detect_failure(), test_aws_controls_evaluate(), test_gcp_control_flags_internet_ssh(), test_gcp_controls_evaluate(), test_workspace_controls_evaluate(), test_workspace_flags_external_sharing_and_high_risk_oauth()

### Community 120 - "template"
Cohesion: 0.39
Nodes (8): spec, spec, spec, app, matchLabels, replicas, selector, template

### Community 121 - "AssessmentsPage.tsx"
Cohesion: 0.28
Nodes (8): assessmentsApi, Assessment, AssessmentCard(), AssessmentRun, AssessmentsPage(), FRAMEWORK_LABELS, FRAMEWORK_OPTIONS, RunStatusIcon()

### Community 122 - "ExecutiveDashboard.tsx"
Cohesion: 0.17
Nodes (13): recharts@^3.10.1, cardStyle, CloudDashboard(), CloudsResponse, FindingCounts, ProviderSummary, scoreColor(), StateCounts (+5 more)

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
Cohesion: 0.25
Nodes (7): Service unimonitor-redis, Service unimonitor-postgres, apiVersion, kind, apiVersion, kind, metadata

### Community 131 - "Deployment unimonitor-beat"
Cohesion: 0.29
Nodes (6): apiVersion, kind, apiVersion, kind, Deployment unimonitor-worker, Deployment unimonitor-redis

### Community 132 - "_FakeHTTP"
Cohesion: 0.22
Nodes (8): aws_data(), _FakeHTTP, gcp_data(), gws_data(), _run(), test_aws_without_sdk_returns_empty(), test_gcp_without_token_returns_empty(), test_workspace_without_token_returns_empty()

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
Cohesion: 0.22
Nodes (9): PersistentVolumeClaim unimonitor-reports, apiVersion, kind, spec, storage, requests, accessModes, resources (+1 more)

### Community 139 - "test_merged_features.py"
Cohesion: 0.29
Nodes (5): test_report_download_uses_the_generated_file_map(), test_triage_and_priority_queue(), test_zero_trust_endpoint_reports_all_pillars(), TestHtmlReport, Report

### Community 140 - "Secret unimonitor-postgres-secret"
Cohesion: 0.33
Nodes (6): Secret unimonitor-postgres-secret, apiVersion, kind, stringData, type, password

### Community 141 - "volumeClaimTemplates"
Cohesion: 0.18
Nodes (11): requests, accessModes, replicas, resources, serviceName, template, volumeClaimTemplates, spec (+3 more)

### Community 142 - "extended.py"
Cohesion: 0.11
Nodes (14): collected(), FakeGraph, collect_cloud_apps(), collect_copilot_studio(), collect_defender_identity(), collect_defender_office(), collect_ediscovery(), collect_insider_risk() (+6 more)

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
Cohesion: 0.22
Nodes (9): PersistentVolumeClaim unimonitor-redis-data, apiVersion, kind, metadata, spec, storage, requests, accessModes (+1 more)

### Community 148 - "test_control_library.py"
Cohesion: 0.10
Nodes (7): _isolated_vault(), controls(), test_every_control_evaluates(), TestPillars, FrameworkMeta, get_framework(), list_frameworks()

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

### Community 153 - "pytest"
Cohesion: 0.09
Nodes (16): TestDashboardViews, _finding(), test_alert_policy_triggers_and_workflow(), test_audit_chain_detects_tampering(), test_audit_entry_digest_is_stable(), test_collection_schedule_reports_interval(), test_global_search_finds_findings_alerts_and_controls(), test_licensing_maps_seats() (+8 more)

### Community 154 - "tasks/notifications.py"
Cohesion: 0.11
Nodes (7): TestSendWeeklyDigests, evaluate_all_tenants(), evaluate_alert_policies(), _run_async(), _run_async(), send_weekly_digests(), _run()

### Community 157 - "onboarding.py"
Cohesion: 0.09
Nodes (16): _certificate_payload(), CompleteRequest, connect(), connect_google_service_account(), create_admin(), FirstAdmin, GoogleServiceAccountRequest, microsoft_device_code() (+8 more)

### Community 163 - "cloud_providers.py"
Cohesion: 0.23
Nodes (6): _aws_snapshot(), collect_aws(), collect_gcp(), collect_google_workspace(), _google_token_from_store(), _rest()

### Community 176 - "create_app"
Cohesion: 0.10
Nodes (5): _build_spa(), TestSpaServing, create_app(), _spa_directory(), SpaFallbackMiddleware

### Community 177 - "oauth_callback"
Cohesion: 0.15
Nodes (5): TestGetEntraUserInfo, login(), oauth_callback(), sso_status(), get_entra_user_info()

### Community 178 - "ReportsPage.tsx"
Cohesion: 0.29
Nodes (7): reportsApi, FORMAT_LABELS, FORMAT_OPTIONS, Report, ReportsPage(), RunReportSummary, StatusIcon()

### Community 179 - "ExecutiveDashboard.tsx"
Cohesion: 0.32
Nodes (7): ExecutiveDashboard(), FrameworkCoverage, ScoreGauge(), StatCard(), tooltipStyle, TopRisk, TrendPoint

### Community 180 - "httpx"
Cohesion: 0.15
Nodes (11): fake_validate(), assume_role_credentials(), _call(), _boto3(), CloudError, _google_token(), validate_aws(), _call() (+3 more)

### Community 181 - "Base"
Cohesion: 0.09
Nodes (13): upgrade(), upgrade(), upgrade(), Base, set_sqlite_pragma(), Control, ControlMapping, Framework (+5 more)

### Community 184 - "RiskDashboard.tsx"
Cohesion: 0.40
Nodes (5): cellColor(), LEVELS, RiskCell, RiskDashboard(), TopFinding

### Community 188 - "generate_report_task"
Cohesion: 0.19
Nodes (4): ReportStatus, HtmlReportGenerator, generate_report_task(), _run_async()

### Community 189 - "acquire_token_for_client"
Cohesion: 0.26
Nodes (5): _run(), TestAcquireTokenForClient, TestExchangeCodeForToken, acquire_token_for_client(), exchange_code_for_token()

### Community 190 - "PlatformConnector.tsx"
Cohesion: 0.11
Nodes (29): AuthMethodPicker(), Certificate, CertificateFiles, Connection, DeviceCode, Field(), GoogleSharedConnector(), inputStyle (+21 more)

### Community 191 - "dependencies.py"
Cohesion: 0.22
Nodes (7): get_current_active_user(), require_admin(), require_analyst(), require_compliance(), require_role(), _check(), AuthorisationError

### Community 192 - "FindingsPage.tsx"
Cohesion: 0.18
Nodes (12): findingsApi, Finding, FindingListResponse, FindingsPage(), PriorityItem, remediationText(), selectStyle, SEVERITIES (+4 more)

### Community 194 - "google_auth.py"
Cohesion: 0.25
Nodes (4): _CachedToken, GoogleAuthError, mint_access_token(), _parse_key()

### Community 205 - "logging.py"
Cohesion: 0.06
Nodes (17): get_audit_logger(), get_logger(), log_audit_event(), AzureSecurityCollector, AzureSecurityData, CopilotCollector, CopilotData, DefenderCollector (+9 more)

## Knowledge Gaps
- **1 isolated node(s):** `unimonitor`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 1713 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **66 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GraphClient` connect `GraphClient` to `asyncio`, `.get`, `Tenant`, `get_settings`, `RateLimiter`, `logging.py`, `extended.py`, `monitoring.py`, `client.py`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `GraphClient` (e.g. with `TestBatchGet` and `TestEnsureToken`) actually correct?**
  _`GraphClient` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `unimonitor` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `asyncio` be split into smaller, more focused modules?**
  _Cohesion score 0.08672659968270756 - nodes in this community are weakly interconnected._
- **Why does `get_settings()` connect `get_settings` to `AIRemediationEngine`, `test_core_logging.py`, `service.py`, `security.py`, `test_auth_and_cli.py`, `grc.py`, `pytest`, `tasks/notifications.py`, `onboarding.py`, `auth.py`, `RateLimiter`, `cloud_providers.py`, `core/cache.py`, `create_app`, `oauth_callback`, `monitoring.py`, `Base`, `acquire_token_for_client`, `config.py`, `test_extended_collectors.py`, `BaseReportGenerator`, `logging.py`, `client.py`, `test_reporting.py`, `test_onboarding.py`, `m365.py`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Should `.get` be split into smaller, more focused modules?**
  _Cohesion score 0.08548168249660787 - nodes in this community are weakly interconnected._
- **Why does `get_current_user()` connect `grc.py` to `auth.py`, `dashboard_overview`, `v1/alerts.py`, `dashboard.py`, `Tenant`, `FindingRepository`, `search.py`, `get_current_user`, `test_auth_and_cli.py`, `conftest.py`, `monitoring.py`, `v1/notifications.py`, `AssessmentRun`, `client.py`, `reports.py`, `dependencies.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._