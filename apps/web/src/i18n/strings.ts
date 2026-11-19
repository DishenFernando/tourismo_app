// Foundation architecture only: unreviewed translations should never be used for safety-critical content.
export const supportedLocales = ['en', 'si', 'ta'] as const
export type Locale = typeof supportedLocales[number]
export const strings = {
  en: { explore:'Discover', plan:'Plan a trip', login:'Log in', heading:'Find your kind of Sri Lanka', tagline:'A beautiful trip starts with the right information.', guest:'Explore freely. No account needed.', search:'Search destinations...' },
  si: { explore:'සොයා බලන්න', plan:'සංචාරය සැලසුම් කරන්න', login:'ඇතුළු වන්න', heading:'ශ්‍රී ලංකාව ගවේෂණය කරන්න', tagline:'ඔබේ ගමන සැලසුම් කරන්න.', guest:'ගිණුමක් අවශ්‍ය නැත.', search:'ගමනාන්ත සොයන්න...' },
  ta: { explore:'கண்டறியுங்கள்', plan:'பயணத்தைத் திட்டமிடுங்கள்', login:'உள்நுழைக', heading:'இலங்கையை ஆராயுங்கள்', tagline:'உங்கள் பயணத்தைத் திட்டமிடுங்கள்.', guest:'கணக்கு தேவையில்லை.', search:'இடங்களைத் தேடுங்கள்...' }
}
// Localization infrastructure; critical destination narratives require separately reviewed translations.
