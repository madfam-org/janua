package main

import (
	"context"
	"fmt"
	"log"
	"os"

	janua "github.com/madfam-io/go-sdk/client"
	"github.com/madfam-io/go-sdk/models"
)

func main() {
	// Initialize the Janua client
	client := janua.New(janua.Config{
		BaseURL: getEnv("JANUA_API_URL", "https://api.janua.dev"),
		APIKey:  getEnv("JANUA_API_KEY", ""),
	})

	ctx := context.Background()

	// Example 1: Sign up a new user
	fmt.Println("=== Sign Up Example ===")
	signUpReq := &models.SignUpRequest{
		Email:    "user@example.com",
		Password: "SecurePassword123!",
		Name:     "Test User",
	}

	authResp, err := client.SignUp(ctx, signUpReq)
	if err != nil {
		log.Printf("Sign up failed: %v", err)
	} else {
		fmt.Printf("User created: %s\n", authResp.User.Email)
		fmt.Printf("Access token: %s...\n", authResp.AccessToken[:20])
	}

	// Example 2: Sign in
	fmt.Println("\n=== Sign In Example ===")
	authResp, err = client.SignIn(ctx, "user@example.com", "SecurePassword123!")
	if err != nil {
		log.Fatalf("Sign in failed: %v", err)
	}
	fmt.Printf("Signed in as: %s\n", authResp.User.Email)

	// Example 3: Get user information
	fmt.Println("\n=== Get User Example ===")
	user, err := client.GetUser(ctx)
	if err != nil {
		log.Printf("Get user failed: %v", err)
	} else {
		fmt.Printf("User ID: %s\n", user.ID)
		fmt.Printf("Email: %s\n", user.Email)
		fmt.Printf("Email Verified: %v\n", user.EmailVerified)
		fmt.Printf("MFA Enabled: %v\n", user.MFAEnabled)
	}

	// Example 4: Update user
	fmt.Println("\n=== Update User Example ===")
	name := "Updated Name"
	locale := "en-US"
	updateReq := &models.UserUpdate{
		Name:   &name,
		Locale: &locale,
	}

	updatedUser, err := client.UpdateUser(ctx, updateReq)
	if err != nil {
		log.Printf("Update user failed: %v", err)
	} else {
		fmt.Printf("Updated name: %s\n", updatedUser.Name)
	}

	// Example 5: List sessions
	fmt.Println("\n=== List Sessions Example ===")
	sessions, err := client.ListSessions(ctx)
	if err != nil {
		log.Printf("List sessions failed: %v", err)
	} else {
		fmt.Printf("Active sessions: %d\n", len(sessions))
		for _, session := range sessions {
			fmt.Printf("- Session ID: %s, Device: %s, IP: %s\n",
				session.ID, session.Device, session.IPAddress)
		}
	}

	// Example 6: Enable MFA
	fmt.Println("\n=== Enable MFA Example ===")
	mfaSetup, err := client.EnableMFA(ctx)
	if err != nil {
		log.Printf("Enable MFA failed: %v", err)
	} else {
		fmt.Printf("MFA Secret: %s\n", mfaSetup.Secret)
		fmt.Printf("QR Code: %s\n", mfaSetup.QRCode[:50]+"...")
		fmt.Printf("Recovery codes: %d\n", len(mfaSetup.RecoveryCodes))
	}

	// Example 7: Sign out
	fmt.Println("\n=== Sign Out Example ===")
	err = client.SignOut(ctx)
	if err != nil {
		log.Printf("Sign out failed: %v", err)
	} else {
		fmt.Println("Successfully signed out")
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}