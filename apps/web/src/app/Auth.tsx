import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { ClerkProvider, useAuth, useClerk } from '@clerk/react'

type AuthValue = {
  enabled: boolean; signedIn: boolean; loaded: boolean;
  login: () => void; logout: () => Promise<void>; token: () => Promise<string|null>
}
const noAuth: AuthValue = { enabled:false, signedIn:false, loaded:true, login:()=>{}, logout: async()=>{}, token:async()=>null }
const AuthContext = createContext<AuthValue>(noAuth)
export const useTourismoAuth = () => useContext(AuthContext)

function ConnectedAuth({children}:{children:ReactNode}) {
  const { isSignedIn, isLoaded, getToken, signOut } = useAuth()
  const clerk = useClerk()
  const value = useMemo<AuthValue>(() => ({
    enabled:true, signedIn:!!isSignedIn, loaded:isLoaded,
    login:() => clerk.openSignIn(),
    logout:() => signOut(), token:() => getToken()
  }), [isSignedIn, isLoaded, getToken, signOut, clerk])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function AuthenticationProvider({children}:{children:ReactNode}) {
  const key = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
  if (!key) return <AuthContext.Provider value={noAuth}>{children}</AuthContext.Provider>
  return <ClerkProvider publishableKey={key} appearance={{variables:{colorPrimary:'#086d69',colorBackground:'#fcf9f3',colorForeground:'#082739'}}}><ConnectedAuth>{children}</ConnectedAuth></ClerkProvider>
}
