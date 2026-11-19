import { Link } from 'react-router-dom'
export function Footer() {
  return <footer className="mt-20 border-t border-ink/10 bg-[#f4f9f5] print:hidden"><div className="wrap grid gap-8 py-10 sm:grid-cols-3">
    <div><img src="/brand/Tourismo_Logo_Horizontal_Vector.svg" className="w-44" alt="Tourismo"/><p className="text-sm text-ink/60 mt-3">Discover Sri Lanka with clarity, curiosity, and confidence.</p></div>
    <div><h3 className="font-bold mb-3">Explore</h3><p><Link to="/discover">Destinations</Link> · <Link to="/plan">Trip planner</Link></p><p className="text-sm text-ink/60 mt-2">Accommodation, guides, food and transport are planned for later phases.</p></div>
    <div><h3 className="font-bold mb-3">Built on trust</h3><p className="text-sm text-ink/60">Phase 1 foundation · Example editorial place records only. No live provider availability, fares, booking or payment.</p></div>
  </div></footer>
}
