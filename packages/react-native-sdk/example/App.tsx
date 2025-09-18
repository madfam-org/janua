/**
 * Plinto React Native SDK Example App
 * Demonstrates all authentication features
 */

import React, { useState, useEffect } from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Alert,
  StyleSheet,
  ActivityIndicator,
  Platform,
  Switch,
} from 'react-native';
import PlintoClient from '@plinto/react-sdk-native';
import * as Keychain from 'react-native-keychain';
import { Linking } from 'react-native';

// Initialize Plinto client
const plinto = new PlintoClient({
  baseURL: 'https://api.plinto.dev',
  tenantId: 'YOUR_TENANT_ID',
  clientId: 'YOUR_CLIENT_ID',
  redirectUri: 'plinto-example://auth/callback',
});

const App: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [mfaCode, setMfaCode] = useState('');
  const [biometricEnabled, setBiometricEnabled] = useState(false);
  const [sessions, setSessions] = useState<any[]>([]);
  const [organizations, setOrganizations] = useState<any[]>([]);

  useEffect(() => {
    checkAuthStatus();
    setupDeepLinking();
  }, []);

  const setupDeepLinking = () => {
    // Handle OAuth callback
    Linking.addEventListener('url', handleDeepLink);
    Linking.getInitialURL().then((url) => {
      if (url) handleDeepLink({ url });
    });
  };

  const handleDeepLink = ({ url }: { url: string }) => {
    if (url.includes('auth/callback')) {
      const params = new URLSearchParams(url.split('?')[1]);
      const code = params.get('code');
      const state = params.get('state');
      if (code && state) {
        handleOAuthCallback(code, state);
      }
    }
  };

  const checkAuthStatus = async () => {
    try {
      const currentUser = await plinto.auth.getCurrentUser();
      if (currentUser) {
        setUser(currentUser);
        await loadUserData();
      }
    } catch (error) {
      console.log('Not authenticated');
    }
  };

  const loadUserData = async () => {
    try {
      const [userSessions, userOrgs] = await Promise.all([
        plinto.sessions.listSessions(),
        plinto.organizations.listOrganizations(),
      ]);
      setSessions(userSessions);
      setOrganizations(userOrgs);
    } catch (error) {
      // Error handled silently in production
    }
  };

  const handleSignUp = async () => {
    setLoading(true);
    try {
      const result = await plinto.auth.signUp({
        email,
        password,
        firstName,
        lastName,
      });
      setUser(result.user);
      Alert.alert('Success', 'Account created successfully!');
      await loadUserData();
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSignIn = async () => {
    setLoading(true);
    try {
      const result = await plinto.auth.signIn({ email, password });
      setUser(result.user);
      Alert.alert('Success', 'Signed in successfully!');
      await loadUserData();
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    setLoading(true);
    try {
      await plinto.auth.signOut();
      setUser(null);
      setSessions([]);
      setOrganizations([]);
      Alert.alert('Success', 'Signed out successfully!');
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = async (provider: string) => {
    try {
      const authUrl = await plinto.auth.signInWithProvider(provider);
      await Linking.openURL(authUrl);
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  const handleOAuthCallback = async (code: string, state: string) => {
    setLoading(true);
    try {
      const result = await plinto.auth.handleOAuthCallback(code, state);
      setUser(result.user);
      Alert.alert('Success', 'Signed in with social provider!');
      await loadUserData();
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEnableMFA = async () => {
    setLoading(true);
    try {
      const result = await plinto.auth.enableMFA();
      Alert.alert(
        'MFA Setup',
        `Scan this QR code with your authenticator app:\n${result.qr_code}\n\nRecovery codes:\n${result.recovery_codes.join('\n')}`,
      );
      setMfaEnabled(true);
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyMFA = async () => {
    setLoading(true);
    try {
      await plinto.auth.verifyMFA(mfaCode, 'challenge_id');
      Alert.alert('Success', 'MFA verified successfully!');
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEnableBiometric = async () => {
    try {
      const biometryType = await Keychain.getSupportedBiometryType();
      if (!biometryType) {
        Alert.alert('Error', 'Biometric authentication not supported on this device');
        return;
      }

      const result = await plinto.auth.enableBiometric();
      setBiometricEnabled(true);
      Alert.alert('Success', `${biometryType} authentication enabled!`);
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  const handleBiometricSignIn = async () => {
    setLoading(true);
    try {
      const result = await plinto.auth.signInWithBiometric();
      setUser(result.user);
      Alert.alert('Success', 'Signed in with biometric authentication!');
      await loadUserData();
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await plinto.sessions.revokeSession(sessionId);
      Alert.alert('Success', 'Session revoked');
      await loadUserData();
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  const handleCreateOrganization = async () => {
    try {
      const org = await plinto.organizations.createOrganization({
        name: 'New Organization',
        description: 'Created from mobile app',
      });
      Alert.alert('Success', `Organization "${org.name}" created!`);
      await loadUserData();
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  const handlePasswordReset = async () => {
    try {
      await plinto.auth.requestPasswordReset(email);
      Alert.alert('Success', 'Password reset email sent!');
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <ActivityIndicator size="large" color="#6366f1" />
          <Text style={styles.loadingText}>Loading...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!user) {
    return (
      <SafeAreaView style={styles.container}>
        <ScrollView contentInsetAdjustmentBehavior="automatic">
          <View style={styles.authContainer}>
            <Text style={styles.title}>Plinto Auth Example</Text>
            
            <TextInput
              style={styles.input}
              placeholder="Email"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
            />
            
            <TextInput
              style={styles.input}
              placeholder="Password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
            />
            
            <TextInput
              style={styles.input}
              placeholder="First Name (for signup)"
              value={firstName}
              onChangeText={setFirstName}
            />
            
            <TextInput
              style={styles.input}
              placeholder="Last Name (for signup)"
              value={lastName}
              onChangeText={setLastName}
            />
            
            <TouchableOpacity style={styles.button} onPress={handleSignIn}>
              <Text style={styles.buttonText}>Sign In</Text>
            </TouchableOpacity>
            
            <TouchableOpacity style={styles.button} onPress={handleSignUp}>
              <Text style={styles.buttonText}>Sign Up</Text>
            </TouchableOpacity>
            
            <TouchableOpacity style={styles.linkButton} onPress={handlePasswordReset}>
              <Text style={styles.linkText}>Forgot Password?</Text>
            </TouchableOpacity>
            
            <View style={styles.divider}>
              <Text style={styles.dividerText}>Or sign in with</Text>
            </View>
            
            <View style={styles.socialButtons}>
              <TouchableOpacity
                style={styles.socialButton}
                onPress={() => handleSocialLogin('google')}
              >
                <Text style={styles.socialButtonText}>Google</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={styles.socialButton}
                onPress={() => handleSocialLogin('github')}
              >
                <Text style={styles.socialButtonText}>GitHub</Text>
              </TouchableOpacity>
            </View>
            
            {biometricEnabled && (
              <TouchableOpacity style={styles.biometricButton} onPress={handleBiometricSignIn}>
                <Text style={styles.buttonText}>Sign In with Biometric</Text>
              </TouchableOpacity>
            )}
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentInsetAdjustmentBehavior="automatic">
        <View style={styles.profileContainer}>
          <Text style={styles.title}>Welcome, {user.first_name}!</Text>
          <Text style={styles.subtitle}>{user.email}</Text>
          
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Security Settings</Text>
            
            <View style={styles.settingRow}>
              <Text>Multi-Factor Authentication</Text>
              <Switch
                value={mfaEnabled}
                onValueChange={(value) => {
                  if (value) {
                    handleEnableMFA();
                  }
                }}
              />
            </View>
            
            {mfaEnabled && (
              <View style={styles.mfaVerify}>
                <TextInput
                  style={styles.input}
                  placeholder="Enter MFA code"
                  value={mfaCode}
                  onChangeText={setMfaCode}
                  keyboardType="number-pad"
                />
                <TouchableOpacity style={styles.smallButton} onPress={handleVerifyMFA}>
                  <Text style={styles.buttonText}>Verify</Text>
                </TouchableOpacity>
              </View>
            )}
            
            <View style={styles.settingRow}>
              <Text>Biometric Authentication</Text>
              <Switch
                value={biometricEnabled}
                onValueChange={(value) => {
                  if (value) {
                    handleEnableBiometric();
                  }
                }}
              />
            </View>
          </View>
          
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Active Sessions</Text>
            {sessions.map((session) => (
              <View key={session.id} style={styles.sessionCard}>
                <View style={styles.sessionInfo}>
                  <Text style={styles.sessionDevice}>{session.device}</Text>
                  <Text style={styles.sessionLocation}>{session.location}</Text>
                  <Text style={styles.sessionTime}>{session.created_at}</Text>
                </View>
                <TouchableOpacity
                  style={styles.revokeButton}
                  onPress={() => handleRevokeSession(session.id)}
                >
                  <Text style={styles.revokeButtonText}>Revoke</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
          
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Organizations</Text>
            {organizations.map((org) => (
              <View key={org.id} style={styles.orgCard}>
                <Text style={styles.orgName}>{org.name}</Text>
                <Text style={styles.orgRole}>{org.role}</Text>
              </View>
            ))}
            <TouchableOpacity style={styles.button} onPress={handleCreateOrganization}>
              <Text style={styles.buttonText}>Create Organization</Text>
            </TouchableOpacity>
          </View>
          
          <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut}>
            <Text style={styles.signOutButtonText}>Sign Out</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f9fafb',
  },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#6b7280',
  },
  authContainer: {
    padding: 20,
  },
  profileContainer: {
    padding: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 5,
  },
  subtitle: {
    fontSize: 16,
    color: '#6b7280',
    marginBottom: 30,
  },
  input: {
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 8,
    padding: 12,
    marginBottom: 15,
    fontSize: 16,
    backgroundColor: 'white',
  },
  button: {
    backgroundColor: '#6366f1',
    borderRadius: 8,
    padding: 15,
    alignItems: 'center',
    marginBottom: 10,
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  linkButton: {
    alignItems: 'center',
    marginTop: 10,
  },
  linkText: {
    color: '#6366f1',
    fontSize: 14,
  },
  divider: {
    alignItems: 'center',
    marginVertical: 20,
  },
  dividerText: {
    color: '#6b7280',
    fontSize: 14,
  },
  socialButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  socialButton: {
    flex: 1,
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    marginHorizontal: 5,
  },
  socialButtonText: {
    color: '#111827',
    fontSize: 14,
    fontWeight: '500',
  },
  biometricButton: {
    backgroundColor: '#10b981',
    borderRadius: 8,
    padding: 15,
    alignItems: 'center',
  },
  section: {
    marginBottom: 30,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 15,
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  mfaVerify: {
    flexDirection: 'row',
    marginTop: 10,
  },
  smallButton: {
    backgroundColor: '#6366f1',
    borderRadius: 8,
    paddingHorizontal: 20,
    paddingVertical: 10,
    marginLeft: 10,
  },
  sessionCard: {
    backgroundColor: 'white',
    borderRadius: 8,
    padding: 15,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 1,
    },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  sessionInfo: {
    flex: 1,
  },
  sessionDevice: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  sessionLocation: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 2,
  },
  sessionTime: {
    fontSize: 12,
    color: '#9ca3af',
    marginTop: 2,
  },
  revokeButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  revokeButtonText: {
    color: '#ef4444',
    fontSize: 14,
    fontWeight: '500',
  },
  orgCard: {
    backgroundColor: 'white',
    borderRadius: 8,
    padding: 15,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 1,
    },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  orgName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
  },
  orgRole: {
    fontSize: 14,
    color: '#6b7280',
    marginTop: 4,
  },
  signOutButton: {
    backgroundColor: '#ef4444',
    borderRadius: 8,
    padding: 15,
    alignItems: 'center',
    marginTop: 20,
  },
  signOutButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default App;