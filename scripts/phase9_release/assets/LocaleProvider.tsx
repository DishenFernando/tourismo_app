/** Phase 9A: interface-label translations, not a claim that editorial content is translated. */
import {createContext, useContext, useEffect, useState, type PropsWithChildren} from 'react'

export type Locale = 'en' | 'si' | 'ta'
type LocaleValue = {locale: Locale; setLocale: (next: Locale) => void}
const LocaleContext = createContext<LocaleValue | null>(null)
const KEY = 'tourismo.interface-language.v1'

function loadLocale(): Locale {
  try {
    const value = window.localStorage.getItem(KEY)
    return value === 'si' || value === 'ta' ? value : 'en'
  } catch {
    return 'en'
  }
}

export function LocaleProvider({children}: PropsWithChildren) {
  const [locale, setLocale] = useState<Locale>(loadLocale)
  useEffect(() => {
    try {window.localStorage.setItem(KEY, locale)} catch { /* storage may be blocked */ }
    document.documentElement.dataset.interfaceLocale = locale
    // Most destination/vendor and app content is still English. Keep its document language
    // accurate until there is native-reviewed full-page translation, not only nav labels.
    document.documentElement.lang = 'en'
  }, [locale])
  return <LocaleContext.Provider value={{locale, setLocale}}>{children}</LocaleContext.Provider>
}

export function useLocale(): LocaleValue {
  const ctx = useContext(LocaleContext)
  if (!ctx) throw new Error('useLocale must be used inside LocaleProvider')
  return ctx
}

const nav: Record<Locale, Record<string, string>> = {
  en: {
    '/': 'Home', '/discover': 'Discover', '/map': 'Map', '/listings': 'Services',
    '/plan': 'Plan trip', '/saved': 'Saved trips', '/enquiries': 'Enquiries',
    '/vendors': 'For businesses',
  },
  si: {
    '/': 'මුල් පිටුව', '/discover': 'සොයා බලන්න', '/map': 'සිතියම', '/listings': 'සේවා',
    '/plan': 'සංචාරය සැලසුම් කරන්න', '/saved': 'සුරැකි සංචාර', '/enquiries': 'විමසීම්',
    '/vendors': 'ව්‍යාපාර සඳහා',
  },
  ta: {
    '/': 'முகப்பு', '/discover': 'கண்டறியுங்கள்', '/map': 'வரைபடம்', '/listings': 'சேவைகள்',
    '/plan': 'பயணத் திட்டம்', '/saved': 'சேமித்த பயணங்கள்', '/enquiries': 'விசாரணைகள்',
    '/vendors': 'வணிகங்களுக்கு',
  },
}

export function navLabel(locale: Locale, path: string, fallback: string): string {
  return nav[locale][path] ?? fallback
}
