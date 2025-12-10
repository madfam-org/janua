package cmd

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/spf13/cobra"

	"github.com/madfam/enclii/packages/cli/internal/config"
)

// LocalConfig holds paths to infrastructure and service directories
type LocalConfig struct {
	LabspacePath     string
	FoundryPath      string
	SharedComposePath string
	JanuaPath        string
	EncliiPath       string
}

func NewLocalCommand(cfg *config.Config) *cobra.Command {
	localCmd := &cobra.Command{
		Use:   "local",
		Short: "Manage local MADFAM development environment",
		Long: `Manage the local MADFAM development environment.

This command orchestrates the shared foundry infrastructure (PostgreSQL, Redis, MinIO)
and all ecosystem services (Janua, Enclii, etc.) to mirror production topology.

The local environment uses:
  - Shared PostgreSQL with per-app databases (janua_dev, enclii_dev, etc.)
  - Shared Redis with per-app DB indices
  - Shared MinIO for object storage
  - Shared MailHog for email testing

Port Allocation (MADFAM Standard):
  4100-4199: Janua (API: 4100, Dashboard: 4101, Admin: 4102, Docs: 4103, Website: 4104)
  4200-4299: Enclii (API: 4200, UI: 4201)
  5432: PostgreSQL (shared)
  6379: Redis (shared)
  9000/9001: MinIO (shared)
  8025: MailHog UI (shared)`,
	}

	localCmd.AddCommand(NewLocalUpCommand(cfg))
	localCmd.AddCommand(NewLocalDownCommand(cfg))
	localCmd.AddCommand(NewLocalStatusCommand(cfg))
	localCmd.AddCommand(NewLocalLogsCommand(cfg))
	localCmd.AddCommand(NewLocalInfraCommand(cfg))

	return localCmd
}

// getLocalConfig resolves paths relative to labspace
func getLocalConfig() (*LocalConfig, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, fmt.Errorf("failed to get home directory: %w", err)
	}

	labspacePath := filepath.Join(home, "labspace")
	foundryPath := filepath.Join(labspacePath, "solarpunk-foundry")
	
	return &LocalConfig{
		LabspacePath:     labspacePath,
		FoundryPath:      foundryPath,
		SharedComposePath: filepath.Join(foundryPath, "ops", "local", "docker-compose.shared.yml"),
		JanuaPath:        filepath.Join(labspacePath, "janua"),
		EncliiPath:       filepath.Join(labspacePath, "enclii"),
	}, nil
}

// ============================================
// enclii local up
// ============================================

func NewLocalUpCommand(cfg *config.Config) *cobra.Command {
	var services []string
	var skipInfra bool

	cmd := &cobra.Command{
		Use:   "up [services...]",
		Short: "Start local MADFAM development environment",
		Long: `Start the local MADFAM development environment.

By default, starts shared infrastructure and all core services.
You can specify individual services to start.

Examples:
  enclii local up                    # Start everything
  enclii local up --skip-infra       # Start services only (infra already running)
  enclii local up janua              # Start only Janua services
  enclii local up janua enclii       # Start Janua and Enclii
  enclii local up infra              # Start only infrastructure`,
		RunE: func(cmd *cobra.Command, args []string) error {
			services = args
			return localUp(cfg, services, skipInfra)
		},
	}

	cmd.Flags().BoolVar(&skipInfra, "skip-infra", false, "Skip starting shared infrastructure")

	return cmd
}

func localUp(cfg *config.Config, services []string, skipInfra bool) error {
	localCfg, err := getLocalConfig()
	if err != nil {
		return err
	}

	fmt.Println("╔══════════════════════════════════════════════════════════════╗")
	fmt.Println("║           ENCLII LOCAL DEVELOPMENT ENVIRONMENT              ║")
	fmt.Println("║              Mirroring Production Topology                  ║")
	fmt.Println("╚══════════════════════════════════════════════════════════════╝")
	fmt.Println()

	// Phase 1: Start shared infrastructure
	if !skipInfra && (len(services) == 0 || contains(services, "infra")) {
		fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
		fmt.Println("  Phase 1: Starting Shared Infrastructure")
		fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
		
		if err := startInfrastructure(localCfg); err != nil {
			return fmt.Errorf("failed to start infrastructure: %w", err)
		}
		
		// Wait for infrastructure to be healthy
		if err := waitForInfrastructure(); err != nil {
			return fmt.Errorf("infrastructure health check failed: %w", err)
		}
	}

	// Phase 2: Start Janua services
	if len(services) == 0 || contains(services, "janua") {
		fmt.Println()
		fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
		fmt.Println("  Phase 2: Starting Janua (Authentication Platform)")
		fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
		
		if err := startJanua(localCfg); err != nil {
			return fmt.Errorf("failed to start Janua: %w", err)
		}
	}

	// Phase 3: Start Enclii services
	if len(services) == 0 || contains(services, "enclii") {
		fmt.Println()
		fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
		fmt.Println("  Phase 3: Starting Enclii (DevOps Platform)")
		fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
		
		if err := startEnclii(localCfg); err != nil {
			return fmt.Errorf("failed to start Enclii: %w", err)
		}
	}

	// Print status summary
	fmt.Println()
	fmt.Println("╔══════════════════════════════════════════════════════════════╗")
	fmt.Println("║                   LOCAL ENVIRONMENT READY                   ║")
	fmt.Println("╚══════════════════════════════════════════════════════════════╝")
	fmt.Println()
	printServiceTable()
	
	return nil
}

func startInfrastructure(localCfg *LocalConfig) error {
	fmt.Println("→ Starting PostgreSQL, Redis, MinIO, MailHog...")
	
	cmd := exec.Command("docker", "compose", "-f", localCfg.SharedComposePath, "up", "-d")
	cmd.Dir = localCfg.FoundryPath
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	
	if err := cmd.Run(); err != nil {
		return err
	}
	
	fmt.Println("✓ Infrastructure containers started")
	return nil
}

func waitForInfrastructure() error {
	fmt.Println("→ Waiting for services to be healthy...")
	
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	// Wait for PostgreSQL
	for {
		select {
		case <-ctx.Done():
			return fmt.Errorf("timeout waiting for PostgreSQL")
		default:
			cmd := exec.Command("docker", "exec", "madfam-postgres-shared", "pg_isready", "-U", "madfam")
			if err := cmd.Run(); err == nil {
				fmt.Println("✓ PostgreSQL ready")
				goto redisCheck
			}
			time.Sleep(1 * time.Second)
		}
	}

redisCheck:
	// Wait for Redis
	for {
		select {
		case <-ctx.Done():
			return fmt.Errorf("timeout waiting for Redis")
		default:
			cmd := exec.Command("docker", "exec", "madfam-redis-shared", "redis-cli", "-a", "redis_dev_password", "ping")
			if out, _ := cmd.Output(); string(out) == "PONG\n" {
				fmt.Println("✓ Redis ready")
				return nil
			}
			time.Sleep(1 * time.Second)
		}
	}
}

func startJanua(localCfg *LocalConfig) error {
	apiPath := filepath.Join(localCfg.JanuaPath, "apps", "api")
	
	// Run migrations
	fmt.Println("→ Running Janua database migrations...")
	migrateCmd := exec.Command(
		filepath.Join(apiPath, ".venv", "bin", "alembic"),
		"upgrade", "head",
	)
	migrateCmd.Dir = apiPath
	migrateCmd.Env = append(os.Environ(),
		"DATABASE_URL=postgresql://janua:janua_dev@localhost:5432/janua_dev",
	)
	if err := migrateCmd.Run(); err != nil {
		fmt.Println("⚠ Migration warning (may already be applied):", err)
	} else {
		fmt.Println("✓ Migrations applied")
	}

	// Start API
	fmt.Println("→ Starting Janua API on port 4100...")
	apiCmd := exec.Command(
		filepath.Join(apiPath, ".venv", "bin", "uvicorn"),
		"app.main:app",
		"--host", "0.0.0.0",
		"--port", "4100",
	)
	apiCmd.Dir = apiPath
	apiCmd.Env = append(os.Environ(),
		"DATABASE_URL=postgresql://janua:janua_dev@localhost:5432/janua_dev",
		"REDIS_URL=redis://:redis_dev_password@localhost:6379/0",
		"ADMIN_BOOTSTRAP_PASSWORD=YS9V9CK!qmR2s&",
		"ENABLE_BETA_ENDPOINTS=false",
	)
	
	if err := apiCmd.Start(); err != nil {
		return fmt.Errorf("failed to start Janua API: %w", err)
	}
	fmt.Println("✓ Janua API starting (PID:", apiCmd.Process.Pid, ")")

	// Start frontend apps (in background)
	frontendApps := []struct {
		name string
		port string
		path string
	}{
		{"Dashboard", "4101", "apps/dashboard"},
		{"Admin", "4102", "apps/admin"},
		{"Docs", "4103", "apps/docs"},
		{"Website", "4104", "apps/website"},
	}

	for _, app := range frontendApps {
		fmt.Printf("→ Starting Janua %s on port %s...\n", app.name, app.port)
		appPath := filepath.Join(localCfg.JanuaPath, app.path)
		
		cmd := exec.Command("pnpm", "dev", "--", "-p", app.port)
		cmd.Dir = appPath
		cmd.Env = append(os.Environ(), "PORT="+app.port)
		
		if err := cmd.Start(); err != nil {
			fmt.Printf("⚠ Failed to start %s: %v\n", app.name, err)
		} else {
			fmt.Printf("✓ %s starting (PID: %d)\n", app.name, cmd.Process.Pid)
		}
	}

	return nil
}

func startEnclii(localCfg *LocalConfig) error {
	apiPath := filepath.Join(localCfg.EncliiPath, "apps", "switchyard-api")
	
	fmt.Println("→ Starting Enclii API on port 4200...")
	
	cmd := exec.Command("go", "run", "./cmd/api")
	cmd.Dir = apiPath
	cmd.Env = append(os.Environ(),
		"ENCLII_PORT=4200",
		"ENCLII_DATABASE_URL=postgres://enclii:enclii_dev@localhost:5432/enclii_dev?sslmode=disable",
		"ENCLII_REDIS_HOST=localhost",
		"ENCLII_REDIS_PASSWORD=redis_dev_password",
		"ENCLII_AUTH_MODE=local",
		"ENCLII_JANUA_URL=http://localhost:4100",
	)
	
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start Enclii API: %w", err)
	}
	fmt.Println("✓ Enclii API starting (PID:", cmd.Process.Pid, ")")

	return nil
}

func printServiceTable() {
	fmt.Println("┌─────────────────────┬───────┬─────────────────────────────────┐")
	fmt.Println("│ Service             │ Port  │ URL                             │")
	fmt.Println("├─────────────────────┼───────┼─────────────────────────────────┤")
	fmt.Println("│ PostgreSQL          │ 5432  │ postgres://madfam@localhost     │")
	fmt.Println("│ Redis               │ 6379  │ redis://localhost               │")
	fmt.Println("│ MinIO               │ 9000  │ http://localhost:9001 (console) │")
	fmt.Println("│ MailHog             │ 8025  │ http://localhost:8025           │")
	fmt.Println("├─────────────────────┼───────┼─────────────────────────────────┤")
	fmt.Println("│ Janua API           │ 4100  │ http://localhost:4100           │")
	fmt.Println("│ Janua Dashboard     │ 4101  │ http://localhost:4101           │")
	fmt.Println("│ Janua Admin         │ 4102  │ http://localhost:4102           │")
	fmt.Println("│ Janua Docs          │ 4103  │ http://localhost:4103           │")
	fmt.Println("│ Janua Website       │ 4104  │ http://localhost:4104           │")
	fmt.Println("├─────────────────────┼───────┼─────────────────────────────────┤")
	fmt.Println("│ Enclii API          │ 4200  │ http://localhost:4200           │")
	fmt.Println("│ Enclii UI           │ 4201  │ http://localhost:4201           │")
	fmt.Println("└─────────────────────┴───────┴─────────────────────────────────┘")
	fmt.Println()
	fmt.Println("Admin credentials: admin@madfam.io / YS9V9CK!qmR2s&")
}

// ============================================
// enclii local down
// ============================================

func NewLocalDownCommand(cfg *config.Config) *cobra.Command {
	var keepInfra bool

	cmd := &cobra.Command{
		Use:   "down",
		Short: "Stop local MADFAM development environment",
		Long:  "Stop all local services and optionally keep infrastructure running.",
		RunE: func(cmd *cobra.Command, args []string) error {
			return localDown(cfg, keepInfra)
		},
	}

	cmd.Flags().BoolVar(&keepInfra, "keep-infra", false, "Keep infrastructure running")

	return cmd
}

func localDown(cfg *config.Config, keepInfra bool) error {
	fmt.Println("Stopping local MADFAM environment...")

	// Kill Node.js processes on Janua ports
	for _, port := range []string{"4100", "4101", "4102", "4103", "4104", "4200", "4201"} {
		cmd := exec.Command("lsof", "-ti:"+port)
		if out, err := cmd.Output(); err == nil && len(out) > 0 {
			killCmd := exec.Command("kill", "-9", string(out[:len(out)-1]))
			killCmd.Run()
			fmt.Printf("✓ Stopped process on port %s\n", port)
		}
	}

	// Stop infrastructure if not keeping
	if !keepInfra {
		localCfg, _ := getLocalConfig()
		fmt.Println("→ Stopping infrastructure containers...")
		cmd := exec.Command("docker", "compose", "-f", localCfg.SharedComposePath, "down")
		cmd.Dir = localCfg.FoundryPath
		cmd.Run()
		fmt.Println("✓ Infrastructure stopped")
	}

	fmt.Println("✓ Local environment stopped")
	return nil
}

// ============================================
// enclii local status
// ============================================

func NewLocalStatusCommand(cfg *config.Config) *cobra.Command {
	return &cobra.Command{
		Use:   "status",
		Short: "Show status of local MADFAM services",
		RunE: func(cmd *cobra.Command, args []string) error {
			return localStatus(cfg)
		},
	}
}

func localStatus(cfg *config.Config) error {
	fmt.Println("Checking local MADFAM environment status...")
	fmt.Println()

	// Check infrastructure
	fmt.Println("Infrastructure:")
	checkService("PostgreSQL", "docker exec madfam-postgres-shared pg_isready -U madfam")
	checkService("Redis", "docker exec madfam-redis-shared redis-cli -a redis_dev_password ping")
	checkService("MinIO", "curl -sf http://localhost:9000/minio/health/live")
	checkService("MailHog", "curl -sf http://localhost:8025")

	fmt.Println()
	fmt.Println("Janua Services:")
	checkHTTP("Janua API", "http://localhost:4100/health")
	checkHTTP("Dashboard", "http://localhost:4101")
	checkHTTP("Admin", "http://localhost:4102")
	checkHTTP("Docs", "http://localhost:4103")
	checkHTTP("Website", "http://localhost:4104")

	fmt.Println()
	fmt.Println("Enclii Services:")
	checkHTTP("Enclii API", "http://localhost:4200/health")
	checkHTTP("Enclii UI", "http://localhost:4201")

	return nil
}

func checkService(name, command string) {
	cmd := exec.Command("sh", "-c", command)
	if err := cmd.Run(); err != nil {
		fmt.Printf("  ❌ %s: not running\n", name)
	} else {
		fmt.Printf("  ✓ %s: running\n", name)
	}
}

func checkHTTP(name, url string) {
	cmd := exec.Command("curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", url)
	out, err := cmd.Output()
	if err != nil || string(out) == "000" {
		fmt.Printf("  ❌ %s: not responding\n", name)
	} else {
		fmt.Printf("  ✓ %s: %s\n", name, string(out))
	}
}

// ============================================
// enclii local logs
// ============================================

func NewLocalLogsCommand(cfg *config.Config) *cobra.Command {
	var follow bool

	cmd := &cobra.Command{
		Use:   "logs [service]",
		Short: "View logs for local MADFAM services",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			service := ""
			if len(args) > 0 {
				service = args[0]
			}
			return localLogs(cfg, service, follow)
		},
	}

	cmd.Flags().BoolVarP(&follow, "follow", "f", false, "Follow log output")

	return cmd
}

func localLogs(cfg *config.Config, service string, follow bool) error {
	localCfg, _ := getLocalConfig()
	
	args := []string{"compose", "-f", localCfg.SharedComposePath, "logs"}
	if follow {
		args = append(args, "-f")
	}
	if service != "" {
		args = append(args, service)
	}

	cmd := exec.Command("docker", args...)
	cmd.Dir = localCfg.FoundryPath
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	
	return cmd.Run()
}

// ============================================
// enclii local infra
// ============================================

func NewLocalInfraCommand(cfg *config.Config) *cobra.Command {
	return &cobra.Command{
		Use:   "infra",
		Short: "Start only shared infrastructure (PostgreSQL, Redis, MinIO)",
		RunE: func(cmd *cobra.Command, args []string) error {
			localCfg, err := getLocalConfig()
			if err != nil {
				return err
			}
			
			fmt.Println("Starting shared MADFAM infrastructure...")
			if err := startInfrastructure(localCfg); err != nil {
				return err
			}
			if err := waitForInfrastructure(); err != nil {
				return err
			}
			
			fmt.Println()
			fmt.Println("Infrastructure ready. Connection details:")
			fmt.Println("  PostgreSQL: postgres://madfam:madfam_dev_password@localhost:5432")
			fmt.Println("  Redis: redis://:redis_dev_password@localhost:6379")
			fmt.Println("  MinIO: http://localhost:9000 (admin/minioadmin)")
			fmt.Println("  MailHog: http://localhost:8025")
			
			return nil
		},
	}
}

// Utility functions

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
