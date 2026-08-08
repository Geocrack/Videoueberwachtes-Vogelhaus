import { Moon, Sun } from 'lucide-react'

import { useTheme } from '../hooks/use-theme.ts'

type ThemeToggleProps = {
    className?: string
}

function ThemeToggle({ className = '' }: ThemeToggleProps) {
    const { theme, toggleTheme } = useTheme()

    const isDark = theme === 'dark'
    const label = isDark ? 'Zum hellen Design wechseln' : 'Zum dunklen Design wechseln'

    return (
        <button
            type="button"
            onClick={toggleTheme}
            title={label}
            aria-label={label}
            className={`btn btn-ghost btn-circle btn-sm sm:btn-md ${className}`}
        >
            {isDark
                ? <Sun className="size-5" aria-hidden="true" />
                : <Moon className="size-5" aria-hidden="true" />}
        </button>
    )
}

export default ThemeToggle
