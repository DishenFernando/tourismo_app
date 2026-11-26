/** Phase 9A: accessibility utilities and conservative client-side metadata. */
import {useEffect, useState, type MouseEvent} from 'react'
import {Link, useLocation} from 'react-router-dom'
import {useLocale, type Locale} from '../i18n/LocaleProvider'

type PageMeta = {title: string; description: string; isPrivate: boolean}
const SITE = 'Tourismo'
const BLURB = 'Explore Sri Lankan destinations and publicly listed tourism services. Plan a trip before contacting a provider.'

function pageMetadata(path: string): PageMeta {
  const isPrivate = /^\/(?:account|saved|enquiries|vendor|vendors|admin|demo)(?:\/|$)/.test(path) || path === '/plan'
  if (isPrivate) return {title: `Account and service tools | ${SITE}`, description: 'A private Tourismo application area.', isPrivate: true}
  const name = path === '/' ? 'Explore Sri Lanka'
    : path.startsWith('/destinations/') ? 'Destination guide'
    : path === '/discover' ? 'Discover destinations'
    : path === '/map' ? 'Explore the map'
    : path === '/nearby' ? 'Nearby places'
    : path.startsWith('/listings/') ? 'Tourism service information'
    : path === '/listings' ? 'Tourism services'
    : path === '/accessibility' ? 'Accessibility and language support'
    : 'Tourismo page'
  return {title: `${name} | ${SITE}`, description: BLURB, isPrivate: false}
}

function managedMeta(name: string): HTMLMetaElement {
  let node = document.head.querySelector<HTMLMetaElement>(`meta[name="${name}"][data-tourismo-managed="true"]`)
  if (!node && name === 'description') {
    node = document.head.querySelector<HTMLMetaElement>('meta[name="description"]')
  }
  if (!node) {
    node = document.createElement('meta')
    node.name = name
    node.dataset.tourismoManaged = 'true'
    document.head.appendChild(node)
  }
  return node
}

export function RouteMetadata() {
  const {pathname} = useLocation()
  const [announcement, setAnnouncement] = useState('')
  useEffect(() => {
    const metadata = pageMetadata(pathname)
    document.title = metadata.title
    // Existing server-provided descriptions are left untouched; this route-specific
    // description is managed separately and can be replaced by prerendering in Phase 9B.
    managedMeta('description').content = metadata.description
    const robots = document.head.querySelector<HTMLMetaElement>('meta[name="robots"][data-tourismo-managed="true"]')
    const canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"][data-tourismo-managed="true"]')
    if (metadata.isPrivate) {
      managedMeta('robots').content = 'noindex, nofollow'
      canonical?.remove()
    } else {
      robots?.remove()
      // Never claim localhost or HTTP preview as the canonical public domain.
      if (window.location.protocol === 'https:' && !/^(localhost|127\.0\.0\.1)$/i.test(window.location.hostname)) {
        let link = canonical
        if (!link) {
          link = document.createElement('link')
          link.rel = 'canonical'
          link.dataset.tourismoManaged = 'true'
          document.head.appendChild(link)
        }
        link.href = `${window.location.origin}${pathname}`
      } else {
        canonical?.remove()
      }
    }
    setAnnouncement(metadata.title)
  }, [pathname])
  return <span role="status" aria-live="polite" aria-atomic="true" className="sr-only">{announcement}</span>
}

export function SkipToContent() {
  function focusContent(event: MouseEvent<HTMLAnchorElement>) {
    const main = document.getElementById('tourismo-content')
    if (main) {
      event.preventDefault()
      main.focus()
      main.scrollIntoView({block: 'start'})
    }
  }
  return <a href="#tourismo-content" onClick={focusContent}
    className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded-lg focus:bg-white focus:px-5 focus:py-3 focus:text-ink focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-pine">
    Skip to main content
  </a>
}

const langHelp: Record<Locale, string> = {
  en: 'Navigation labels preview. Destination and provider content is still in English.',
  si: 'සංචරණ ලේබල් අත්හදා බැලීමකි. ගමනාන්ත විස්තර තවමත් ඉංග්‍රීසියෙන් ඇත.',
  ta: 'வழிசெலுத்தல் பெயர்கள் மட்டும் முன்னோட்டம். இட விவரங்கள் இன்னும் ஆங்கிலத்தில் உள்ளன.',
}

export function LocaleToolbar() {
  const {locale, setLocale} = useLocale()
  return <section aria-label="Language and accessibility tools" className="border-b border-ink/10 bg-white/70">
    <div className="wrap flex flex-wrap items-center justify-end gap-x-4 gap-y-2 py-2 text-sm">
      <span className="text-ink/65" lang={locale}>{langHelp[locale]}</span>
      <label className="flex items-center gap-2 font-medium" htmlFor="tourismo-locale">
        <span>Language</span>
        <select id="tourismo-locale" aria-label="Interface navigation language" value={locale}
          onChange={event => setLocale(event.target.value as Locale)}
          className="min-h-11 rounded-lg border border-ink/30 bg-white px-3 py-2 text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pine">
          <option value="en" lang="en">English</option>
          <option value="si" lang="si">සිංහල (preview)</option>
          <option value="ta" lang="ta">தமிழ் (முன்னோட்டம்)</option>
        </select>
      </label>
      <Link to="/accessibility" className="inline-flex min-h-11 items-center rounded-lg px-2 underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pine">Accessibility</Link>
    </div>
  </section>
}
