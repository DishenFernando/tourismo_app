import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ClerkProvider, useAuth, useClerk, useUser } from '@clerk/react'
import { bootstrapProfile, getProfile, type TourismoProfile } from '../lib/api'

type AuthValue = {
  enabled: boolean
  signedIn: boolean
  loaded: boolean
  login: () => void
  logout: () => Promise<void>
  manageAccount: () => void
  token: () => Promise<string|null>
  profile: TourismoProfile | null
  profileState: 'idle'|'syncing'|'ready'|'error'
  profileError: string
  refreshProfile: () => Promise<void>
  setProfile: (value: TourismoProfile) => void
  person: { name: string; email: string | null; avatar: string | null } | null
}
const noAuth: AuthValue = {
  enabled:false, signedIn:false, loaded:true, login:()=>{}, logout:async()=>{},
  manageAccount:()=>{}, token:async()=>null, profile:null, profileState:'idle',
  profileError:'', refreshProfile:async()=>{}, setProfile:()=>{}, person:null
}
const AuthContext = createContext<AuthValue>(noAuth)
export const useTourismoAuth = () => useContext(AuthContext)

function ConnectedAuth({children}:{children:ReactNode}) {
  const { isSignedIn, isLoaded, getToken, signOut, userId } = useAuth()
  const {user:clerkUser} = useUser()
  const clerk = useClerk()
  const [profile,setProfile] = useState<TourismoProfile|null>(null)
  const [profileState,setProfileState] = useState<AuthValue['profileState']>('idle')
  const [profileError,setProfileError] = useState('')

  const refreshProfile = useCallback(async () => {
    const jwt = await getToken()
    if (!jwt) throw new Error('Your session is unavailable. Please sign in again.')
    setProfile(await getProfile(jwt))
    setProfileState('ready')
    setProfileError('')
  },[getToken])

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !userId) {
      setProfile(null)
      setProfileState('idle')
      setProfileError('')
      return
    }
    let active = true
    // Clerk verifies identity; backend provisions the unique Tourismo user as soon as login finishes.
    setProfile(null)
    setProfileState('syncing')
    setProfileError('')
    void (async () => {
      try {
        const jwt = await getToken()
        if (!jwt) throw new Error('Session token unavailable')
        const saved = await bootstrapProfile(jwt)
        if (active) {setProfile(saved);setProfileState('ready')}
      } catch (error) {
        if (active) {
          setProfileState('error')
          setProfileError(error instanceof Error ? error.message : 'Profile synchronization failed')
        }
      }
    })()
    return () => {active=false}
  },[isLoaded,isSignedIn,userId,getToken])

  const person = useMemo(() => clerkUser ? ({
    name: profile?.display_name || clerkUser.fullName || clerkUser.firstName || 'Traveler',
    email: clerkUser.primaryEmailAddress?.emailAddress || profile?.email || null,
    avatar: clerkUser.imageUrl || null
  }) : null, [clerkUser, profile])
  const value = useMemo<AuthValue>(() => ({
    enabled:true, signedIn:!!isSignedIn, loaded:isLoaded,
    login:()=>clerk.openSignIn(),
    logout:()=>signOut(),
    manageAccount:()=>clerk.openUserProfile(),
    token:()=>getToken(), profile, profileState, profileError,
    refreshProfile, setProfile, person
  }), [isSignedIn,isLoaded,getToken,signOut,clerk,profile,profileState,profileError,refreshProfile,person])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function AuthenticationProvider({children}:{children:ReactNode}) {
  const key = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
  if (!key) return <AuthContext.Provider value={noAuth}>{children}</AuthContext.Provider>
  return <ClerkProvider publishableKey={key} appearance={{variables:{colorPrimary:'#086d69',colorBackground:'#fcf9f3',colorForeground:'#082739'}}}><ConnectedAuth>{children}</ConnectedAuth></ClerkProvider>
}
