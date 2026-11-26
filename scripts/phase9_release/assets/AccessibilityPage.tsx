import {Link} from 'react-router-dom'

export function AccessibilityPage() {
  return <main className="wrap py-12 max-w-4xl" id="phase9-accessibility">
    <p className="small-label">TOURISMO · ACCESSIBILITY</p>
    <h1 className="page-title mt-3">Accessibility and language support</h1>
    <p className="mt-5 text-lg leading-relaxed">Tourismo aims to make Sri Lanka travel planning usable with a keyboard, assistive technologies and smaller screens. This page describes current support and remaining work; it is not a claim of WCAG certification.</p>
    <section className="mt-8 space-y-3" aria-labelledby="language-coverage">
      <h2 className="text-xl font-bold" id="language-coverage">Language coverage</h2>
      <p>English is currently the primary language of destination, business and application content. The language selector offers a <strong>preview of navigation labels</strong> in Sinhala and Tamil. Full translated guides, vendor-provided text and legal notices are not available yet. We will only publish destination translations after native-speaker review and source checks.</p>
      <p>Changing the navigation language does not alter pricing, rankings, provider verification or availability.</p>
    </section>
    <section className="mt-8 space-y-3" aria-labelledby="keyboard-help">
      <h2 className="text-xl font-bold" id="keyboard-help">Keyboard and screen-reader basics</h2>
      <ul className="list-disc pl-6 space-y-2"><li>Press Tab at the top of a page to find the “Skip to main content” link.</li><li>Use Tab and Shift+Tab to move between controls and Enter or Space to activate them.</li><li>The language selector is a native keyboard-operable control.</li><li>Maps should have a usable list alternative; if a map action lacks one, treat that as an accessibility issue to report.</li></ul>
    </section>
    <section className="mt-8 space-y-3" aria-labelledby="known-gaps">
      <h2 className="text-xl font-bold" id="known-gaps">Known limitations</h2>
      <p>We have not completed a full assistive-technology audit, content translation, contrast verification at every breakpoint or production search-engine pre-rendering. Some older forms and map interactions may need additional work.</p>
      <p>Please describe accessibility issues through the contact methods published on the relevant Tourismo page. Avoid including passwords, identification documents or payment information in feedback.</p>
    </section>
    <Link to="/discover" className="btn-secondary mt-9 inline-flex">Back to destinations</Link>
  </main>
}
