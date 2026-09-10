import { Info, Settings } from 'lucide-react'
import { Link } from 'react-router'

import ThemeToggle from './theme-toggle.tsx'

function Header() {
    return (
        <header className="sticky top-0 z-30 w-full border-b border-border bg-bg/85 backdrop-blur">
            <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-3 sm:h-16 sm:gap-3 sm:px-6 lg:px-8 2xl:max-w-[96rem]">
                <h1 className="min-w-0 flex-1 truncate text-base font-semibold tracking-tight text-heading sm:text-lg md:text-xl lg:text-2xl">
                    <Link to="/livestream" className="hover:opacity-80">
                        Videoüberwachtes Vogelhaus
                    </Link>
                </h1>

                <nav aria-label="Hauptaktionen" className="flex shrink-0 items-center gap-0.5 sm:gap-1">
                    <ThemeToggle />
                </nav>
            </div>
        </header>
    )
}

export default Header;
